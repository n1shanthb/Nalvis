"""Persist KG ingest → workspaces + agents (deterministic inventory + audited proposals)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from aip.config import settings
from aip.db.orm import AgentGuardrailRow, AgentRow, ContextDocumentRow, WorkspaceRow
from aip.db.repo import ensure_company
from aip.db.serializers import context_to_api, workspace_to_api
from aip.kg.auditor import audit_agent_proposals
from aip.kg.inventory import build_inventory_from_kg, parse_preview_from_inventory
from aip.kg.synthesizer import propose_agents_from_inventory, synthesized_at
from aip.policy.engine import seed_workspace_policies


def _slug(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s or f"ws-{uuid4().hex[:8]}"


def ingest_context(
    session: Session,
    *,
    raw: str,
    source: str = "paste",
    name: str | None = None,
) -> dict[str, Any]:
    ensure_company(session, "default")
    inv = build_inventory_from_kg(raw)
    if inv.company_name:
        ensure_company(session, "default", inv.company_name)

    preview = parse_preview_from_inventory(inv)
    workspace_ids: list[str] = []
    workspaces_out: list[dict[str, Any]] = []

    products = list(inv.products) or (["default"] if inv.resources else [])
    for product in products:
        ws_id = f"ws-{_slug(product)}"
        repos = [
            r.name
            for r in inv.resources
            if r.kind == "repo" and (r.owner_product in (None, product))
        ]
        # Ensure smoke repo in scope when github available and no repos listed
        if not repos and "github" in inv.availability.available:
            owner = (settings.smoke_github_owner or "").strip()
            repo = (settings.smoke_github_repo or "").strip()
            if owner and repo:
                repos = [f"{owner}/{repo}"]
                preview.setdefault("warnings", []).append(
                    f"No repos in KG for {product}; added configured smoke repo to scope"
                )
        jira = [
            r.name
            for r in inv.resources
            if r.kind == "jira_project" and (r.owner_product in (None, product))
        ]
        cals = [
            r.name
            for r in inv.resources
            if r.kind == "calendar" and (r.owner_product in (None, product))
        ]
        if not cals and "calendar" in inv.availability.available:
            cals = ["primary"]
        emails = [
            r.name
            for r in inv.resources
            if r.kind == "email_group" and (r.owner_product in (None, product))
        ]
        if not emails and "gmail" in inv.availability.available and settings.gmail_user:
            emails = [settings.gmail_user]

        existing = session.get(WorkspaceRow, ws_id)
        if existing:
            existing.repo_scope = repos
            existing.jira_scope = jira
            existing.calendar_scope = cals
            existing.comms_scope = emails
            existing.name = product
            existing.product = product
            row = existing
        else:
            row = WorkspaceRow(
                id=ws_id,
                company_id="default",
                name=product,
                product=product,
                description=f"Workspace for {product}",
                repo_scope=repos,
                jira_scope=jira,
                calendar_scope=cals,
                comms_scope=emails,
                metadata_json={"from_kg": True},
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
        session.flush()
        seed_workspace_policies(session, ws_id)
        workspace_ids.append(ws_id)
        workspaces_out.append(workspace_to_api(row))

    # Agent synthesis + audit
    proposals = propose_agents_from_inventory(inv)
    audit = audit_agent_proposals(inv, proposals)

    doc = ContextDocumentRow(
        id=f"ctx-{uuid4().hex[:12]}",
        company_id="default",
        name=name or ("uploaded-context.json" if source == "upload" else "pasted-context.txt"),
        source=source,
        raw=raw,
        parse_preview=preview,
        workspace_ids=workspace_ids,
        parsed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    session.flush()

    agents_created = 0
    for p in audit.accepted:
        ws_ids = []
        if p.workspace_product:
            ws_ids = [f"ws-{_slug(p.workspace_product)}"]
        elif p.role == "ValidationAgent":
            ws_ids = list(workspace_ids)

        # Stable id from role+workspace to allow re-ingest activate-in-place
        agent_id = f"agt-{_slug(p.role)}-{_slug(p.workspace_product or 'company')}"
        existing_agent = session.get(AgentRow, agent_id)
        origin = {
            "contextDocumentId": doc.id,
            "contextDocumentName": doc.name,
            "rationale": p.rationale,
            "kgPaths": p.origin_paths,
            "signals": p.origin_signals,
            "synthesizedAt": synthesized_at(),
        }
        specs = {
            "runtime": "openai-agents",
            "modelHint": "gpt-4.1-mini",
            "maxConcurrency": 2,
            "timeoutSec": 300,
            "memoryKeys": [],
            "inputSchema": ["job_type", "requested_action"],
            "outputSchema": ["evidence", "status"],
            "leastPrivilegeNote": "Tools limited to tool_scope; unsupported agents have none.",
        }
        if existing_agent:
            existing_agent.name = p.name
            existing_agent.role = p.role
            existing_agent.mission = p.mission
            existing_agent.description = p.mission
            existing_agent.tool_scope = p.tool_scope
            existing_agent.workspace_ids = ws_ids
            existing_agent.status = p.status
            existing_agent.activation = p.activation
            existing_agent.system_key = p.system_key
            existing_agent.origin = origin
            existing_agent.specs = specs
            agent_row = existing_agent
        else:
            agent_row = AgentRow(
                id=agent_id,
                name=p.name,
                role=p.role,
                description=p.mission,
                mission=p.mission,
                tool_scope=p.tool_scope,
                workspace_ids=ws_ids,
                status=p.status,
                activation=p.activation,
                system_key=p.system_key,
                origin=origin,
                specs=specs,
                created_at=datetime.now(timezone.utc),
            )
            session.add(agent_row)
            agents_created += 1
        session.flush()

        # Replace synthesized guardrails
        from sqlalchemy import select as sa_select

        for g in session.scalars(
            sa_select(AgentGuardrailRow).where(
                AgentGuardrailRow.agent_id == agent_row.id,
                AgentGuardrailRow.source == "synthesized",
            )
        ).all():
            session.delete(g)
        session.flush()
        for gr in p.default_guardrails:
            session.add(
                AgentGuardrailRow(
                    agent_id=agent_row.id,
                    tool=gr["tool"],
                    mode=gr.get("mode", "allow"),
                    label=gr.get("label", gr["tool"]),
                    rationale=p.rationale,
                    source="synthesized",
                    created_at=datetime.now(timezone.utc),
                )
            )

    session.flush()
    return {
        "document": context_to_api(doc),
        "workspaces": workspaces_out,
        "agents_accepted": len(audit.accepted),
        "agents_rejected": [{"role": p.role, "reason": reason} for p, reason in audit.rejected],
        "agents_created": agents_created,
        "inventory": {
            "products": inv.products,
            "availableConnectors": sorted(inv.availability.available),
            "warnings": inv.warnings,
        },
    }

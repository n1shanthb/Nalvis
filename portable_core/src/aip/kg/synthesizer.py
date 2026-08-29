"""Agent specialization catalog + synthesis proposals (meaning layer).

Catalog entries are Authority specializations — not scenario if-trees.
Without an LLM key, proposals are inventory-grounded catalog instantiations
(system present + scopes exist → specialization templates for that system).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aip.evidence.contracts import EXECUTABLE_SYSTEMS
from aip.kg.inventory import CompanyInventory


@dataclass
class AgentProposal:
    name: str
    role: str
    system_key: str
    mission: str
    tool_scope: list[str]
    workspace_product: str | None
    status: str  # idle | unsupported
    activation: str  # ready | blocked_missing_connector
    origin_paths: list[str] = field(default_factory=list)
    origin_signals: list[str] = field(default_factory=list)
    rationale: str = ""
    job_types: list[str] = field(default_factory=list)
    default_guardrails: list[dict[str, str]] = field(default_factory=list)


# Authority agent types — keyed by system family (general catalog, not examples)
SPECIALIZATION_CATALOG: list[dict[str, Any]] = [
    {
        "role": "GitHubIssueManagerAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub Issue Manager",
        "mission": "Create/triage/label/assign issues within workspace repo scope.",
        "tool_scope": ["github.create_issue", "github.read"],
        "job_types": ["github.create_issue"],
        "guardrails": [
            {"tool": "github.create_issue", "mode": "allow", "label": "Create issues in scope"},
        ],
    },
    {
        "role": "GitHubPRReviewerAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub PR Reviewer",
        "mission": "Add review comments and summarize checks within repo scope.",
        "tool_scope": ["github.review_pr", "github.read"],
        "job_types": ["github.review_pr"],
        "guardrails": [
            {"tool": "github.review_pr", "mode": "hil", "label": "PR review writes"},
        ],
    },
    {
        "role": "GitHubCICDAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub CI/CD",
        "mission": "Propose or create CI workflow changes (typically HIL-gated).",
        "tool_scope": ["github.create_or_update_workflow", "github.read"],
        "job_types": ["github.create_or_update_workflow"],
        "guardrails": [
            {"tool": "github.create_or_update_workflow", "mode": "hil", "label": "CI workflow writes"},
        ],
    },
    {
        "role": "JiraSyncAgent",
        "system": "jira",
        "requires_resource": "jira_project",
        "name_template": "{product} Jira Sync",
        "mission": "Create/link/transition tickets within Jira project scope.",
        "tool_scope": ["jira.create_ticket", "jira.transition_ticket", "jira.read"],
        "job_types": ["jira.create_ticket", "jira.transition_ticket"],
        "guardrails": [
            {"tool": "jira.create_ticket", "mode": "allow", "label": "Create tickets in scope"},
            {"tool": "jira.transition_ticket", "mode": "hil", "label": "Transitions"},
        ],
    },
    {
        "role": "GmailCommsAgent",
        "system": "gmail",
        "requires_resource": "email_group",
        "name_template": "{product} Gmail Comms",
        "mission": "Draft/send emails and triage threads within comms scope.",
        "tool_scope": ["gmail.send_email", "gmail.read"],
        "job_types": ["gmail.send_email"],
        "guardrails": [
            {"tool": "gmail.send_email", "mode": "hil", "label": "External send"},
        ],
    },
    {
        "role": "CalendarSchedulerAgent",
        "system": "calendar",
        "requires_resource": "calendar",
        "name_template": "{product} Calendar Scheduler",
        "mission": "Schedule/reschedule meetings within calendar scope.",
        "tool_scope": ["calendar.create_event", "calendar.update_event", "calendar.read"],
        "job_types": ["calendar.create_event", "calendar.update_event"],
        "guardrails": [
            {"tool": "calendar.create_event", "mode": "allow", "label": "Create events"},
            {"tool": "calendar.update_event", "mode": "hil", "label": "Reschedule"},
        ],
    },
]


def _products(inv: CompanyInventory) -> list[str]:
    return list(inv.products) or ["default"]


def _has_resource(inv: CompanyInventory, product: str, kind: str) -> bool:
    for r in inv.resources:
        if r.kind != kind:
            continue
        if r.owner_product is None or r.owner_product == product:
            return True
    # company-level systems may imply scopes from settings smoke targets later
    return False


def _system_mentioned(inv: CompanyInventory, system: str) -> list[InventoryResource]:
    return [r for r in inv.resources if r.kind == "system" and r.name == system]


def propose_agents_from_inventory(inv: CompanyInventory) -> list[AgentProposal]:
    """
    Propose agents from inventory.

    Prefer LLM when OPENAI_API_KEY is set; otherwise catalog instantiation from
    inventory facts (system presence + resource kinds + connector availability).
    """
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            return _propose_via_llm(inv, api_key)
        except Exception:  # noqa: BLE001
            pass
    return _propose_via_catalog(inv)


def _propose_via_catalog(inv: CompanyInventory) -> list[AgentProposal]:
    proposals: list[AgentProposal] = []
    available = inv.availability.available

    for product in _products(inv):
        for entry in SPECIALIZATION_CATALOG:
            system = entry["system"]
            req = entry["requires_resource"]
            system_hits = _system_mentioned(inv, system)
            has_res = _has_resource(inv, product, req)
            # Instantiate specialization only when inventory shows the system or required resources
            if not (has_res or system_hits):
                continue
            executable = system in available and system in EXECUTABLE_SYSTEMS
            paths = [r.evidence_path for r in system_hits]
            paths += [
                r.evidence_path
                for r in inv.resources
                if r.kind == req and (r.owner_product in (None, product))
            ]
            proposals.append(
                AgentProposal(
                    name=entry["name_template"].format(product=product),
                    role=entry["role"],
                    system_key=system,
                    mission=entry["mission"],
                    tool_scope=list(entry["tool_scope"]) if executable else [],
                    workspace_product=product,
                    status="idle" if executable else "unsupported",
                    activation="ready" if executable else "blocked_missing_connector",
                    origin_paths=paths[:12],
                    origin_signals=[f"system:{system}", f"resource:{req}"],
                    rationale=(
                        f"Catalog specialization for {system} grounded in inventory "
                        f"(available={system in available})."
                    ),
                    job_types=list(entry["job_types"]) if executable else [],
                    default_guardrails=list(entry["guardrails"]) if executable else [],
                )
            )

    # Unsupported stubs for non-executable systems named in inventory
    seen_unsupported: set[tuple[str | None, str]] = set()
    for r in inv.resources:
        if r.kind != "system":
            continue
        if r.name in EXECUTABLE_SYSTEMS:
            # If executable system mentioned but connector unavailable → unsupported stub
            if r.name not in available:
                key = (r.owner_product, r.name)
                if key in seen_unsupported:
                    continue
                seen_unsupported.add(key)
                product = r.owner_product or (_products(inv)[0])
                proposals.append(
                    AgentProposal(
                        name=f"{product} {r.name.title()} Automation",
                        role=f"{r.name.title()}Agent",
                        system_key=r.name,
                        mission=f"Automate {r.name} workflows once a connector is available.",
                        tool_scope=[],
                        workspace_product=product,
                        status="unsupported",
                        activation="blocked_missing_connector",
                        origin_paths=[r.evidence_path],
                        origin_signals=[f"system:{r.name}", "connector:missing"],
                        rationale=f"System {r.name} present in KG but connector not available.",
                    )
                )
            continue
        key = (r.owner_product, r.name)
        if key in seen_unsupported:
            continue
        seen_unsupported.add(key)
        product = r.owner_product or (_products(inv)[0])
        proposals.append(
            AgentProposal(
                name=f"{product} {r.name.title()} Automation",
                role=f"{r.name.title()}Agent",
                system_key=r.name,
                mission=f"Discovered {r.name} automation opportunity; blocked until connector exists.",
                tool_scope=[],
                workspace_product=product,
                status="unsupported",
                activation="blocked_missing_connector",
                origin_paths=[r.evidence_path],
                origin_signals=[f"system:{r.name}", "unsupported"],
                rationale=f"KG names {r.name}; no v1 write tools — unsupported stub.",
            )
        )

    # Always include ValidationAgent (read-only) when any executable system exists
    if available:
        proposals.append(
            AgentProposal(
                name="Validation Agent",
                role="ValidationAgent",
                system_key="validation",
                mission="Re-query external systems to verify evidence; emit PASS/FAIL/NO_EVIDENCE.",
                tool_scope=["validation.read"],
                workspace_product=None,
                status="idle",
                activation="ready",
                origin_paths=["$.platform.validation"],
                origin_signals=["role:ValidationAgent"],
                rationale="Authority-required read-only validator.",
                job_types=[],
                default_guardrails=[
                    {"tool": "validation.read", "mode": "allow", "label": "Read-only validation"},
                ],
            )
        )

    return proposals


def _propose_via_llm(inv: CompanyInventory, api_key: str) -> list[AgentProposal]:
    """LLM proposes specializations; still constrained to catalog + inventory systems."""
    # Keep dependency soft — fall back to catalog if openai package missing
    try:
        from openai import OpenAI
    except ImportError:
        return _propose_via_catalog(inv)

    catalog_roles = [e["role"] for e in SPECIALIZATION_CATALOG] + ["ValidationAgent"]
    systems = sorted({r.name for r in inv.resources if r.kind == "system"})
    products = _products(inv)
    prompt = (
        "You propose automation agent specializations for a company knowledge graph.\n"
        "Return JSON: {\"agents\":[{\"role\":...,\"system_key\":...,\"product\":...,\"mission\":...,"
        "\"rationale\":...}]}.\n"
        f"Allowed roles: {catalog_roles}. You may also propose unsupported stubs for named systems "
        f"not in {sorted(EXECUTABLE_SYSTEMS)}.\n"
        f"Products: {products}. Systems in inventory: {systems}. "
        f"Available connectors now: {sorted(inv.availability.available)}.\n"
        "Do not invent products/repos/systems not in the inventory."
    )
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    import json

    # Strip fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text)
    # Merge LLM meaning with catalog tools via auditor-friendly proposals
    base = { (p.role, p.workspace_product): p for p in _propose_via_catalog(inv) }
    for row in data.get("agents") or []:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "")
        product = row.get("product")
        key = (role, product)
        if key in base:
            base[key].rationale = str(row.get("rationale") or base[key].rationale)
            if row.get("mission"):
                base[key].mission = str(row["mission"])
            continue
        # Unsupported / extra system stub
        system = str(row.get("system_key") or "unknown")
        executable = system in inv.availability.available and system in EXECUTABLE_SYSTEMS
        base[key] = AgentProposal(
            name=f"{product or 'Company'} {role}",
            role=role or f"{system.title()}Agent",
            system_key=system,
            mission=str(row.get("mission") or ""),
            tool_scope=[],
            workspace_product=str(product) if product else None,
            status="idle" if executable else "unsupported",
            activation="ready" if executable else "blocked_missing_connector",
            origin_signals=["llm:proposal"],
            rationale=str(row.get("rationale") or "LLM proposal"),
        )
    return list(base.values())


def synthesized_at() -> str:
    return datetime.now(timezone.utc).isoformat()

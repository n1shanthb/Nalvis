"""GitHub webhook ingress — accept all events; bind Specs via Webhook Catalog."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request

from aip.app_context import ctx
from aip.config import settings
from aip.github_router import extract_context
from aip.webhooks.github_inventory import webhook_id

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def verify_github_signature(secret: str | None, signature_header: str | None, raw: bytes) -> None:
    configured = (secret or "").strip()
    if not configured:
        return
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(401, "Missing or invalid X-Hub-Signature-256")
    digest = hmac.new(configured.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    if not hmac.compare_digest(expected, signature_header.strip()):
        raise HTTPException(401, "Invalid GitHub signature")


def _parse_payload(raw: bytes, content_type: str | None) -> dict[str, Any]:
    ct = (content_type or "").lower()
    if "application/x-www-form-urlencoded" in ct:
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        payload_raw = (form.get("payload") or [""])[0]
        data = json.loads(payload_raw)
    else:
        data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload must be object")
    return data


def _accepts_issue_comment(spec_id: str, is_pull_request: bool) -> bool:
    from aip.inbound.service import accepts_issue_comment

    return accepts_issue_comment(spec_id, is_pull_request)


def _run_bound_spec(spec_id: str, context: dict[str, Any]) -> dict[str, Any]:
    from aip.inbound.service import run_github_spec

    return run_github_spec(spec_id, context)


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    raw = await request.body()
    verify_github_signature(settings.github_webhook_secret, x_hub_signature_256, raw)
    try:
        payload = _parse_payload(raw, request.headers.get("content-type"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Invalid payload: {exc}") from exc

    event = (x_github_event or "unknown").strip().lower()
    action = str(payload.get("action") or "")
    wid = webhook_id(event, action)

    delivery_id = (x_github_delivery or "").strip() or f"local-{wid}-{hash(raw) & 0xFFFFFFFF:08x}"

    # Dedup — allow retry when prior attempt ended in error/queued.
    existing = ctx.webhooks.get_delivery(delivery_id)
    if existing is not None:
        status = str(existing.get("status") or "")
        if status in {"handled", "skipped", "received"}:
            return {"ok": True, "deduped": True, "delivery_id": delivery_id, "status": status}

    context = extract_context(event, payload)
    context["webhook_id"] = wid
    repo = f"{context.get('owner')}/{context.get('repo')}".strip("/")
    from aip.projects.resolve import resolve_github_project

    project = resolve_github_project(context)
    project_id = project.project_id if project else None
    if project_id:
        context["project_id"] = project_id
        context["company_id"] = project.company_id if project else None
    bindings = ctx.webhooks.find_bindings("github", wid, project_id=project_id)
    if not bindings and action:
        bindings = ctx.webhooks.find_bindings(
            "github", webhook_id(event, ""), project_id=project_id
        )
    if wid == "issue_comment.created":
        bindings = [
            b
            for b in bindings
            if _accepts_issue_comment(b.spec_id, bool(context.get("is_pull_request")))
        ]

    from aip.inbound.routing import pick_single_binding

    bindings = pick_single_binding(
        bindings, system="github", webhook_id=wid, context=context
    )
    bound = bool(bindings)
    spec_ids = [b.spec_id for b in bindings if (b.spec_id or "").strip()]

    if existing is None:
        ctx.webhooks.record_delivery(
            delivery_id=delivery_id,
            connected_system_id="github",
            event=event,
            action=action,
            webhook_id=wid,
            repo=repo,
            bound=bound,
            spec_id=spec_ids[0] if spec_ids else None,
            status="queued" if bound else "received",
            payload_summary={
                "number": context.get("number"),
                "title": (context.get("title") or "")[:120],
                "sender": context.get("sender"),
                "conclusion": context.get("conclusion"),
                "workflow_name": context.get("workflow_name"),
                "workflow_run_id": context.get("workflow_run_id"),
                "head_branch": context.get("head_branch"),
                "spec_ids": spec_ids,
            },
        )
    elif bound:
        ctx.webhooks.update_delivery_status(delivery_id, status="queued", error=None)

    ctx.event_bus.emit(
        "github.webhook.received",
        source="github_webhook",
        connected_system_id="github",
        message=f"{wid} on {repo or 'n/a'}",
        payload={
            "webhook_id": wid,
            "delivery_id": delivery_id,
            "bound": bound,
            "spec_ids": spec_ids,
        },
    )

    if not spec_ids:
        return {
            "ok": True,
            "bound": False,
            "webhook_id": wid,
            "delivery_id": delivery_id,
        }

    subject = str(context.get("title") or repo or wid)
    from aip.inbound.jobs import PHASE_AGENT
    from aip.inbound.worker import job_store
    from aip.validation.hooks import open_inbound_watch

    open_inbound_watch(
        delivery_key=delivery_id,
        system="github",
        project_id=str(project_id or ""),
        spec_ids=spec_ids,
        subject=subject,
    )

    context_snapshot = {
        k: context.get(k)
        for k in (
            "owner",
            "repo",
            "number",
            "title",
            "sender",
            "body",
            "webhook_id",
            "project_id",
            "company_id",
            "is_pull_request",
            "conclusion",
            "workflow_name",
            "workflow_run_id",
            "head_branch",
            "sha",
            "html_url",
        )
        if k in context
    }
    for spec_id in spec_ids:
        job_store().enqueue(
            system="github",
            delivery_key=delivery_id,
            spec_id=spec_id,
            project_id=str(project_id or ""),
            phase=PHASE_AGENT,
            payload={"context": context_snapshot},
            force=existing is not None and str(existing.get("status") or "") == "error",
        )

    return {
        "ok": True,
        "bound": True,
        "queued": True,
        "webhook_id": wid,
        "delivery_id": delivery_id,
        "spec_id": spec_ids[0],
        "spec_ids": spec_ids,
    }


def run_github_agent_job(
    *,
    delivery_id: str,
    spec_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible wrapper — prefer inbound.service.execute_agent_job."""
    from aip.inbound.models import InboundAgentCommand
    from aip.inbound.service import execute_agent_job

    return execute_agent_job(
        InboundAgentCommand(
            system="github",
            delivery_key=delivery_id,
            spec_id=spec_id,
            project_id=project_id,
            payload=payload,
        )
    )

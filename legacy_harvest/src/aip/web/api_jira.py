"""Jira webhook ingress — bind Specs via Webhook Catalog; durable inbound jobs."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request

from aip.app_context import ctx
from aip.config import settings
from aip.jira_router import extract_context
from aip.webhooks.jira_inventory import jira_webhook_id

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def verify_jira_secret(
    configured: str | None,
    *,
    query_secret: str | None,
    header_secret: str | None,
) -> None:
    expected = (configured or "").strip()
    if not expected:
        return
    provided = (header_secret or query_secret or "").strip()
    if not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(401, "Invalid or missing Jira webhook secret")


def _run_bound_spec(spec_id: str, context: dict[str, Any]) -> dict[str, Any]:
    from aip.inbound.service import run_jira_spec

    return run_jira_spec(spec_id, context)


@router.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    secret: str | None = Query(default=None),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    x_atlassian_webhook_identifier: str | None = Header(
        default=None, alias="X-Atlassian-Webhook-Identifier"
    ),
) -> dict[str, Any]:
    raw = await request.body()
    verify_jira_secret(
        settings.jira_webhook_secret,
        query_secret=secret,
        header_secret=x_webhook_secret,
    )
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Invalid payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be object")

    context = extract_context(payload)
    wid = str(context.get("webhook_id") or jira_webhook_id("unknown"))
    delivery_id = (
        (x_atlassian_webhook_identifier or "").strip()
        or f"jira-{wid}-{hashlib.sha256(raw).hexdigest()[:16]}"
    )

    existing = ctx.webhooks.get_delivery(delivery_id)
    if existing is not None:
        status = str(existing.get("status") or "")
        if status in {"handled", "skipped", "received"}:
            return {
                "ok": True,
                "deduped": True,
                "delivery_id": delivery_id,
                "status": status,
            }

    from aip.projects.resolve import resolve_jira_project

    project = resolve_jira_project(context)
    project_id = project.project_id if project else None
    if project_id:
        context["project_id"] = project_id
        context["company_id"] = project.company_id if project else None
    bindings = ctx.webhooks.find_bindings("jira", wid, project_id=project_id)
    from aip.inbound.routing import pick_single_binding

    bindings = pick_single_binding(
        bindings, system="jira", webhook_id=wid, context=context
    )
    bound = bool(bindings)
    spec_ids = [b.spec_id for b in bindings if (b.spec_id or "").strip()]
    issue_key = str(context.get("issue_key") or "")

    if existing is None:
        ctx.webhooks.record_delivery(
            delivery_id=delivery_id,
            connected_system_id="jira",
            event=wid,
            action="",
            webhook_id=wid,
            repo=str(context.get("project_key") or ""),
            bound=bound,
            spec_id=spec_ids[0] if spec_ids else None,
            status="queued" if bound else "received",
            payload_summary={
                "issue_key": issue_key,
                "title": (context.get("title") or "")[:120],
                "sender": context.get("sender"),
                "cloud_id": context.get("cloud_id"),
                "spec_ids": spec_ids,
            },
        )
    elif bound:
        ctx.webhooks.update_delivery_status(delivery_id, status="queued", error=None)

    ctx.event_bus.emit(
        "jira.webhook.received",
        source="jira_webhook",
        connected_system_id="jira",
        message=f"{wid} on {issue_key or 'n/a'}",
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

    from aip.inbound.jobs import PHASE_AGENT
    from aip.inbound.worker import job_store
    from aip.validation.hooks import open_inbound_watch

    open_inbound_watch(
        delivery_key=delivery_id,
        system="jira",
        project_id=str(project_id or ""),
        spec_ids=spec_ids,
        subject=str(context.get("title") or issue_key or wid),
    )

    context_snapshot = {
        k: context.get(k)
        for k in (
            "webhook_id",
            "issue_key",
            "issue_id",
            "project_key",
            "title",
            "sender",
            "cloud_id",
            "project_id",
            "company_id",
            "body",
            "status",
            "html_url",
        )
    }

    for spec_id in spec_ids:
        job_store().enqueue(
            system="jira",
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
        "webhook_id": wid,
        "spec_id": spec_ids[0],
        "spec_ids": spec_ids,
        "delivery_id": delivery_id,
        "queued": True,
    }


def run_jira_agent_job(
    *,
    delivery_id: str,
    spec_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from aip.inbound.models import InboundAgentCommand
    from aip.inbound.service import execute_agent_job

    return execute_agent_job(
        InboundAgentCommand(
            system="jira",
            delivery_key=delivery_id,
            spec_id=spec_id,
            project_id=project_id,
            payload=payload,
        )
    )

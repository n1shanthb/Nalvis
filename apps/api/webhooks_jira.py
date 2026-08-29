"""Jira webhook ingress — optional shared-secret check + delivery log."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from aip.config import settings
from apps.api.deliveries import record_delivery

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    x_atlassian_webhook_identifier: str | None = Header(
        default=None, alias="X-Atlassian-Webhook-Identifier"
    ),
) -> dict[str, Any]:
    secret = (settings.jira_webhook_secret or "").strip()
    if secret:
        # Simple shared-secret query/header gate for MVP; tighten with Atlassian JWT later.
        provided = request.query_params.get("secret") or ""
        if provided != secret:
            raise HTTPException(401, "Invalid Jira webhook secret")

    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be object")

    event = str(payload.get("webhookEvent") or payload.get("issue_event_type_name") or "jira")
    issue_key = ""
    issue = payload.get("issue")
    if isinstance(issue, dict):
        issue_key = str(issue.get("key") or "")

    delivery_id = (x_atlassian_webhook_identifier or "").strip() or f"jira-{hash(str(payload)) & 0xFFFFFFFF:08x}"
    row = record_delivery(
        system="jira",
        delivery_id=delivery_id,
        event=event,
        webhook_id=event,
        status="received",
        payload_summary={"issue_key": issue_key},
    )
    logger.info("jira webhook received delivery=%s event=%s", delivery_id, event)
    return {"ok": True, "delivery": row}

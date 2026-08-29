"""API routes for Gmail webhook, watch, and native tool smoke helpers."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from aip.app_context import ctx
from aip.config import settings
from aip.activity.monitor import (
    emit_agent_activated,
    emit_agent_finished,
    emit_agent_received,
)
from aip.gmail.store import GmailWatchStore
from aip.gmail_router import process_message_id, process_pubsub_notification
from aip.tools.gmail import (
    renew_gmail_watch_if_needed,
    search_emails,
    send_email,
    start_gmail_watch,
)

router = APIRouter(prefix="/api")
_watch = GmailWatchStore()


def _check_webhook_secret(
    configured: str | None,
    signature_header: str | None,
    *,
    plain_header: str | None = None,
    body: bytes = b"",
) -> None:
    secret = (configured or "").strip()
    if not secret:
        return
    if plain_header and hmac.compare_digest(plain_header.strip(), secret):
        return
    if signature_header and hmac.compare_digest(signature_header.strip(), secret):
        return
    raise HTTPException(401, "Missing or invalid webhook signature")


@router.get("/gmail/watch")
def gmail_watch_status() -> dict[str, Any]:
    return {"ok": True, "watch": _watch.get()}


@router.post("/gmail/watch")
def gmail_watch_start(force: bool = False) -> dict[str, Any]:
    try:
        if force:
            result = start_gmail_watch()
        else:
            result = renew_gmail_watch_if_needed(force=True)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    if isinstance(result, dict) and result.get("error"):
        detail = str(result.get("detail") or result["error"])
        raise HTTPException(400, detail)
    return result


def _gmail_monitor_context(message_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    result = result or {}
    ctx: dict[str, Any] = {
        "message_id": message_id,
        "title": result.get("subject") or message_id,
        "sender": result.get("from") or "",
        "html_url": "",
        "scope_level": result.get("scope_level") or "company",
    }
    for key in ("company_id", "project_id", "accessed_via_project_id"):
        value = result.get(key)
        if value is not None and str(value).strip():
            ctx[key] = value
    return ctx


def _gmail_monitor_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ignored") or result.get("route") == "skip":
        return {
            "ok": True,
            "skipped": True,
            "reason": result.get("reason") or result.get("route") or "skipped",
        }
    return {
        "ok": bool(result.get("ok")),
        "output": result.get("output"),
        "error": result.get("error"),
        "tool_events": result.get("tool_events") or [],
    }


def _gmail_bound_spec_id(result: dict[str, Any] | None = None) -> str:
    if result and result.get("spec_id"):
        return str(result["spec_id"])
    bindings = ctx.webhooks.find_bindings(
        "gmail", "gmail.message", include_company_global=True
    )
    for binding in bindings:
        if (binding.spec_id or "").strip():
            return binding.spec_id
    return "unbound"


def _trace_gmail_message(
    message_id: str,
    *,
    accessed_via_project_id: str | None = None,
) -> dict[str, Any]:
    spec_id = _gmail_bound_spec_id()
    ctx_hint = _gmail_monitor_context(
        message_id,
        {
            "scope_level": "company",
            "accessed_via_project_id": accessed_via_project_id,
        },
    )
    emit_agent_received(
        ctx.event_bus,
        kind="gmail",
        spec_id=spec_id,
        connected_system_id="gmail",
        context=ctx_hint,
        webhook_id="gmail.message",
        delivery_id=message_id,
    )
    emit_agent_activated(
        ctx.event_bus,
        kind="gmail",
        spec_id=spec_id,
        connected_system_id="gmail",
        context=ctx_hint,
        delivery_id=message_id,
    )
    result = process_message_id(
        message_id, accessed_via_project_id=accessed_via_project_id
    )
    rich_ctx = _gmail_monitor_context(message_id, result)
    emit_agent_finished(
        ctx.event_bus,
        kind="gmail",
        spec_id=str(result.get("spec_id") or spec_id),
        connected_system_id="gmail",
        context=rich_ctx,
        result=_gmail_monitor_result(result),
        delivery_id=message_id,
    )
    return result


@router.post("/webhooks/gmail")
async def gmail_webhook(
    request: Request,
    x_gmail_signature_256: str | None = Header(
        default=None, alias="X-Gmail-Signature-256"
    ),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict[str, Any]:
    body = await request.body()
    _check_webhook_secret(
        settings.gmail_webhook_secret,
        x_gmail_signature_256,
        plain_header=x_webhook_secret,
        body=body,
    )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "JSON body required") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "JSON object required")

    if payload.get("message_id"):
        via = str(
            payload.get("accessed_via_project_id")
            or payload.get("project_id")
            or ""
        ).strip() or None
        result = process_message_id(
            str(payload["message_id"]), accessed_via_project_id=via
        )
        ctx.event_bus.emit(
            "gmail.message_processed",
            source="gmail_webhook",
            connected_system_id="gmail",
            message=f"Enqueued message {payload.get('message_id')}",
            payload=result,
        )
        return result

    result = process_pubsub_notification(payload)
    ctx.event_bus.emit(
        "gmail.pubsub_processed",
        source="gmail_webhook",
        connected_system_id="gmail",
        message=f"Pub/Sub batch size={result.get('count', 0)}",
        payload={"count": result.get("count", 0)},
    )
    return result


@router.post("/gmail/send")
async def gmail_send(payload: dict[str, Any]) -> dict[str, Any]:
    result = send_email(payload)
    if result.get("error"):
        raise HTTPException(400, str(result.get("detail") or result["error"]))
    return result


@router.post("/gmail/search")
async def gmail_search(payload: dict[str, Any]) -> dict[str, Any]:
    result = search_emails(payload)
    if result.get("error"):
        raise HTTPException(400, str(result.get("detail") or result["error"]))
    return result

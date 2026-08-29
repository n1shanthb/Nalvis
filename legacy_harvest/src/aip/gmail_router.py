"""Inbound Gmail router — dedup, skip own/sent, enqueue durable agent jobs."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from aip.activity.monitor import (
    emit_agent_activated,
    emit_agent_finished,
    emit_agent_received,
)
from aip.app_context import ctx
from aip.config import settings
from aip.gmail.store import GmailWatchStore, ProcessedMessageStore
from aip.inbound.jobs import CATCHUP_DELIVERY_KEY, CATCHUP_SPEC_ID, PHASE_AGENT
from aip.inbound.routing import pick_single_binding
from aip.inbound.worker import enqueue_gmail_catchup, job_store
from aip.projects.models import DEFAULT_COMPANY_ID
from aip.runtime.execute_spec import event_message, run_activated_spec
from aip.tools.gmail import fetch_email, list_message_ids_since_history
from aip.webhooks.catalog import WebhookCatalog

logger = logging.getLogger(__name__)

_EMAIL_IN_ANGLE = re.compile(r"<([^>]+)>")
_SKIP_LABELS = frozenset({"SENT", "DRAFT"})
_SKIP_HINTS = re.compile(
    r"(unsubscribe|newsletter|noreply|no-reply|mailer-daemon)", re.I
)

_watch = GmailWatchStore()
_processed = ProcessedMessageStore()
_webhooks = WebhookCatalog()


def _watch_bindings(project_id: str | None = None):
    _webhooks.ensure_tables()
    if not (project_id or "").strip():
        return []
    return _webhooks.find_bindings(
        "gmail", "gmail.message", project_id=project_id.strip()
    )


def _all_project_gmail_bindings() -> list:
    _webhooks.ensure_tables()
    return [
        b
        for b in _webhooks.list_bindings("gmail")
        if b.enabled
        and b.webhook_id == "gmail.message"
        and (b.scope_level or "project").strip().lower() == "project"
        and (b.project_id or "").strip()
    ]


def _resolve_gmail_route(
    message_id: str,
    *,
    accessed_via_project_id: str | None = None,
) -> tuple[str | None, list, dict[str, Any] | None]:
    """Resolve project + single agent binding for one Gmail message."""
    from aip.projects.resolve import resolve_gmail_project

    project_id = (accessed_via_project_id or "").strip() or None
    mail: dict[str, Any] | None = None
    if not project_id:
        mail = fetch_email({"message_id": message_id})
        if mail.get("error"):
            return None, [], mail
        candidates = _all_project_gmail_bindings()
        if candidates:
            binding = pick_single_binding(
                candidates, system="gmail", mail=mail
            )[0]
            return str(binding.project_id or "").strip() or None, [binding], mail
        hit = resolve_gmail_project(
            {
                "mail": mail,
                "to": mail.get("to"),
                "mailbox": settings.gmail_user,
            }
        )
        project_id = hit.project_id if hit is not None else None
    bindings = pick_single_binding(
        _watch_bindings(project_id), system="gmail", mail=mail
    )
    return project_id, bindings, mail


def _extract_email(address: str) -> str:
    raw = (address or "").strip()
    if not raw:
        return ""
    m = _EMAIL_IN_ANGLE.search(raw)
    return (m.group(1) if m else raw).strip().lower()


def should_skip(mail: dict[str, Any]) -> tuple[bool, str]:
    labels = mail.get("label_ids") or mail.get("labelIds") or []
    label_set = {str(x).upper() for x in labels if x}
    if label_set & _SKIP_LABELS:
        return True, "own_outbound_or_sent"
    owner = _extract_email(settings.gmail_user or "")
    if owner and _extract_email(str(mail.get("from") or "")) == owner:
        return True, "from_self"
    from_addr = str(mail.get("from") or "")
    if _SKIP_HINTS.search(from_addr):
        return True, "automated_sender"
    return False, ""


def get_fallback_history() -> str:
    from aip.tools.gmail import get_profile_history_id

    return get_profile_history_id() or ""


def _monitor_context(
    message_id: str,
    mail: dict[str, Any] | None = None,
    *,
    spec_id: str = "",
    project_id: str = "",
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mail = mail or {}
    payload = payload or {}
    result = result or {}
    out: dict[str, Any] = {
        "message_id": message_id,
        "title": mail.get("subject") or result.get("subject") or message_id,
        "sender": mail.get("from") or result.get("from") or "",
        "html_url": "",
        "scope_level": payload.get("scope_level") or result.get("scope_level") or "company",
    }
    for key in ("company_id", "project_id", "accessed_via_project_id"):
        value = (
            payload.get(key)
            or result.get(key)
            or (project_id if key == "project_id" else None)
        )
        if value is not None and str(value).strip():
            out[key] = value
    if spec_id:
        out["spec_id"] = spec_id
    return out


def _monitor_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("skipped"):
        return {
            "ok": True,
            "skipped": True,
            "reason": result.get("reason") or "skipped",
        }
    return {
        "ok": bool(result.get("ok")),
        "output": result.get("output"),
        "error": result.get("error"),
        "tool_events": result.get("tool_events") or [],
    }


def enqueue_gmail_message(
    message_id: str,
    *,
    accessed_via_project_id: str | None = None,
) -> dict[str, Any]:
    """Enqueue agent jobs without Gmail HTTP. Worker fetches the message."""
    message_id = (message_id or "").strip()
    if not message_id:
        return {"ok": False, "ignored": True, "reason": "empty_message_id"}
    if message_id in {CATCHUP_DELIVERY_KEY}:
        return {"ok": True, "ignored": True, "reason": "catchup_key"}
    if _processed.has(message_id):
        return {
            "ok": True,
            "ignored": True,
            "reason": "already_processed",
            "message_id": message_id,
            "queued": False,
            "enqueued": 0,
        }

    via = (accessed_via_project_id or "").strip() or None
    project_id, bindings, _mail = _resolve_gmail_route(
        message_id, accessed_via_project_id=via
    )
    if not bindings:
        # Discovery job: worker fetches and marks unbound/skip.
        job_store().enqueue(
            system="gmail",
            delivery_key=message_id,
            spec_id="",
            project_id=via or project_id or "",
            phase=PHASE_AGENT,
            payload={"accessed_via_project_id": via or project_id},
        )
        return {
            "ok": True,
            "queued": True,
            "enqueued": 1,
            "message_id": message_id,
            "reason": "no_project_binding_pending_fetch",
            "project_id": project_id,
        }

    enqueued = 0
    spec_ids_for_watch: list[str] = []
    for binding in bindings:
        spec_id = (binding.spec_id or "").strip()
        if not spec_id:
            continue
        spec_ids_for_watch.append(spec_id)
        bind_project = str(
            via or project_id or binding.project_id or ""
        ).strip()
        if not bind_project:
            try:
                from aip.runtime.spec_loader import load_spec

                bind_project = str(load_spec(spec_id).agent.org_id or "").strip()
            except Exception:  # noqa: BLE001
                bind_project = ""
        job_store().enqueue(
            system="gmail",
            delivery_key=message_id,
            spec_id=spec_id,
            project_id=bind_project,
            phase=PHASE_AGENT,
            payload={
                "accessed_via_project_id": via or bind_project or binding.project_id,
                "scope_level": "project",
                "company_id": binding.company_id or DEFAULT_COMPANY_ID,
                "project_id": bind_project or binding.project_id,
            },
        )
        enqueued += 1

    if spec_ids_for_watch:
        from aip.validation.hooks import open_inbound_watch

        open_inbound_watch(
            delivery_key=message_id,
            system="gmail",
            project_id=str(via or project_id or ""),
            spec_ids=spec_ids_for_watch,
            subject=message_id,
        )

    return {
        "ok": True,
        "queued": True,
        "enqueued": enqueued,
        "message_id": message_id,
        "project_id": project_id,
    }


def run_gmail_agent_job(
    *,
    message_id: str,
    spec_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible wrapper — worker uses inbound.service.execute_agent_job."""
    from aip.inbound.models import InboundAgentCommand
    from aip.inbound.service import execute_agent_job

    message_id = (message_id or "").strip()
    if not message_id:
        return {"ok": False, "error": "empty_message_id"}

    if _processed.has(message_id) and not spec_id:
        return {"ok": True, "skipped": True, "reason": "already_processed"}

    if not spec_id:
        bindings = _watch_bindings(project_id or None)
        if not bindings:
            _processed.mark(message_id, "unbound")
            return {
                "ok": True,
                "skipped": True,
                "reason": "no_bound_spec",
                "message_id": message_id,
            }
        return enqueue_gmail_message(
            message_id,
            accessed_via_project_id=str(
                payload.get("accessed_via_project_id") or project_id or ""
            )
            or None,
        )

    return execute_agent_job(
        InboundAgentCommand(
            system="gmail",
            delivery_key=message_id,
            spec_id=spec_id,
            project_id=project_id,
            payload=payload,
        )
    )


def process_message_id(
    message_id: str,
    *,
    accessed_via_project_id: str | None = None,
) -> dict[str, Any]:
    """Enqueue durable jobs for a Gmail message (no sync fetch)."""
    return enqueue_gmail_message(
        message_id, accessed_via_project_id=accessed_via_project_id
    )


def process_pubsub_notification(payload: dict[str, Any]) -> dict[str, Any]:
    """Ack-first Pub/Sub: seed cursor if needed, enqueue History catch-up, return fast."""
    message = payload.get("message") if isinstance(payload, dict) else None
    data_b64 = ""
    if isinstance(message, dict):
        data_b64 = str(message.get("data") or "")
    history_id = ""
    if data_b64:
        try:
            decoded = base64.b64decode(data_b64)
            data = json.loads(decoded.decode("utf-8"))
            if isinstance(data, dict):
                history_id = str(data.get("historyId") or "")
        except Exception:  # noqa: BLE001
            history_id = ""
    if not history_id:
        history_id = str(payload.get("historyId") or "")

    state = _watch.get()
    start = state.get("history_id") or ""
    if not start and history_id:
        # Seed from notification id only — no Gmail API on the webhook path.
        _watch.upsert(history_id=history_id)
        return {
            "ok": True,
            "seeded": True,
            "history_id": history_id,
            "processed": [],
            "enqueued": 0,
            "queued_catchup": False,
        }

    enqueue_gmail_catchup(force=False)
    return {
        "ok": True,
        "history_id": start or history_id,
        "processed": [],
        "count": 0,
        "enqueued": 0,
        "queued_catchup": True,
    }

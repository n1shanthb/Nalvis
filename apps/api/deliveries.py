"""In-memory webhook delivery log (Phase connect; replace with Postgres later)."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any

_lock = Lock()
_deliveries: list[dict[str, Any]] = []


def record_delivery(
    *,
    system: str,
    delivery_id: str,
    event: str,
    action: str = "",
    webhook_id: str = "",
    status: str = "received",
    payload_summary: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    row = {
        "system": system,
        "delivery_id": delivery_id,
        "event": event,
        "action": action,
        "webhook_id": webhook_id,
        "status": status,
        "payload_summary": payload_summary or {},
        "error": error,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _deliveries.insert(0, row)
        del _deliveries[200:]
    return row


def list_deliveries(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return list(_deliveries[: max(1, min(limit, 200))])

"""Gmail Pub/Sub push ingress — optional shared secret + delivery log."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from aip.config import settings
from apps.api.deliveries import record_delivery

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request) -> dict[str, Any]:
    secret = (settings.gmail_webhook_secret or "").strip()
    if secret:
        provided = request.query_params.get("secret") or ""
        if provided != secret:
            raise HTTPException(401, "Invalid Gmail webhook secret")

    try:
        envelope = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Invalid JSON: {exc}") from exc

    message = envelope.get("message") if isinstance(envelope, dict) else None
    data_b64 = ""
    if isinstance(message, dict):
        data_b64 = str(message.get("data") or "")
    decoded: dict[str, Any] = {}
    if data_b64:
        try:
            raw = base64.b64decode(data_b64)
            decoded = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            decoded = {"raw": data_b64[:80]}

    history_id = str(decoded.get("historyId") or "")
    email_address = str(decoded.get("emailAddress") or "")
    delivery_id = str((message or {}).get("messageId") if isinstance(message, dict) else "") or (
        f"gmail-{history_id or hash(str(envelope)) & 0xFFFFFFFF:08x}"
    )

    row = record_delivery(
        system="gmail",
        delivery_id=delivery_id,
        event="gmail.message",
        webhook_id="gmail.message",
        status="received",
        payload_summary={"history_id": history_id, "email_address": email_address},
    )
    logger.info("gmail webhook received delivery=%s history_id=%s", delivery_id, history_id)
    return {"ok": True, "delivery": row}

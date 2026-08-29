"""GitHub webhook ingress — signature verify + delivery log (no inbound worker loops)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request

from aip.config import settings
from aip.webhooks.github_inventory import webhook_id
from apps.api.deliveries import record_delivery

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

    repo = ""
    if isinstance(payload.get("repository"), dict):
        repo = str(payload["repository"].get("full_name") or "")

    row = record_delivery(
        system="github",
        delivery_id=delivery_id,
        event=event,
        action=action,
        webhook_id=wid,
        status="received",
        payload_summary={"repo": repo, "action": action},
    )
    logger.info("github webhook received delivery=%s webhook_id=%s", delivery_id, wid)
    return {"ok": True, "delivery": row}

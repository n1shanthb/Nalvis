"""Gmail Pub/Sub push ingress — thin webhook; durable work in Temporal."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from aip.config import settings
from apps.api.deliveries import record_delivery

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


class SimulateGmailInboundBody(BaseModel):
    message_id: str | None = None
    history_id: str | None = None
    subject: str | None = None
    from_addr: str | None = Field(default=None, alias="from")
    snippet: str | None = None
    body_summary: str | None = None
    thread_id: str | None = None
    workspace_ids: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


async def _start_gmail_inbound_workflow(payload: dict[str, Any]) -> str:
    from temporalio.client import Client

    from aip.orchestration.workflows import GmailInboundWorkflow

    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    workflow_id = f"gmail-inbound-{payload.get('delivery_id') or uuid4().hex[:12]}"
    await client.start_workflow(
        GmailInboundWorkflow.run,
        payload,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return workflow_id


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

    workflow_id = None
    start_error = None
    try:
        workflow_id = await _start_gmail_inbound_workflow(
            {
                "history_id": history_id,
                "delivery_id": delivery_id,
                "email_address": email_address,
            }
        )
    except Exception as exc:  # noqa: BLE001
        start_error = str(exc)[:400]
        logger.exception("failed to start GmailInboundWorkflow: %s", exc)

    return {
        "ok": True,
        "delivery": row,
        "temporalWorkflowId": workflow_id,
        "startError": start_error,
    }


@router.post("/webhooks/gmail/simulate")
async def gmail_webhook_simulate(body: SimulateGmailInboundBody) -> dict[str, Any]:
    """Operator/dev path: start inbound run from message_id or a synthetic signal."""
    delivery_id = f"sim-{uuid4().hex[:12]}"
    if body.message_id or body.history_id:
        try:
            workflow_id = await _start_gmail_inbound_workflow(
                {
                    "history_id": body.history_id or "",
                    "message_id": body.message_id or "",
                    "delivery_id": delivery_id,
                    "workspace_ids": body.workspace_ids,
                }
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f"Failed to start GmailInboundWorkflow: {exc}") from exc
        return {"ok": True, "mode": "fetch", "temporalWorkflowId": workflow_id, "delivery_id": delivery_id}

    # Synthetic signal (no Google I/O) — still goes through CompanyRun + Director
    from aip.db.repo import create_run, list_workspaces_api, set_run_workflow
    from aip.db.schema import init_db
    from aip.db.session import session_scope
    from aip.orchestration.workflows import CompanyRunWorkflow
    from temporalio.client import Client

    signal = {
        "channel": "gmail",
        "subject": body.subject or "Inbound simulate",
        "from": body.from_addr or "",
        "snippet": body.snippet or body.body_summary or "",
        "body_summary": body.body_summary or body.snippet or "",
        "thread_id": body.thread_id or "",
        "message_id": "",
        "delivery_id": delivery_id,
    }
    objectives = [f"Inbound gmail: {signal['subject']}"]
    init_db()
    with session_scope() as session:
        ws_ids = list(body.workspace_ids) or [w["id"] for w in list_workspaces_api(session)]
        if not ws_ids:
            raise HTTPException(400, "No workspaces — ingest KG first")
        run = create_run(
            session,
            title=objectives[0][:500],
            objectives=objectives,
            workspace_ids=ws_ids,
            signal=signal,
        )
        run_id = run.id

    workflow_id = f"company-run-{run_id}"
    try:
        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        await client.start_workflow(
            CompanyRunWorkflow.run,
            {
                "run_id": run_id,
                "workspace_ids": ws_ids,
                "objectives": objectives,
                "plan": [],
                "signal": signal,
            },
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"Failed to start CompanyRunWorkflow: {exc}") from exc

    with session_scope() as session:
        set_run_workflow(session, run_id, workflow_id)
    return {
        "ok": True,
        "mode": "synthetic_signal",
        "runId": run_id,
        "temporalWorkflowId": workflow_id,
        "signal": signal,
    }

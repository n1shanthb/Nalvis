"""Repository helpers for control-plane persistence (no synthetic seeds)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from aip.db.orm import (
    AgentGuardrailRow,
    AgentRow,
    ApprovalRow,
    AuditEventRow,
    CompanyRow,
    ContextDocumentRow,
    IntegrationCallRow,
    JobRow,
    PolicyRow,
    RunRow,
    ValidationRow,
    WorkspaceRow,
)
from aip.db.serializers import (
    agent_to_api,
    approval_to_api,
    context_to_api,
    job_to_api,
    policy_group_to_api,
    run_to_api,
    timeline_to_api,
    validation_to_api,
    workspace_to_api,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_company(session: Session, company_id: str = "default", name: str = "") -> CompanyRow:
    row = session.get(CompanyRow, company_id)
    if row is None:
        row = CompanyRow(id=company_id, name=name or "Company")
        session.add(row)
        session.flush()
    elif name and not row.name:
        row.name = name
    return row


def append_audit(
    session: Session,
    *,
    run_id: str,
    kind: str,
    label: str,
    job_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditEventRow:
    evt = AuditEventRow(
        run_id=run_id,
        job_id=job_id,
        kind=kind,
        label=label,
        meta=meta or {},
        at=_utcnow(),
    )
    session.add(evt)
    session.flush()
    return evt


def create_run(
    session: Session,
    *,
    title: str,
    objectives: list[str],
    workspace_ids: list[str],
    plan: list[dict[str, Any]] | None = None,
    signal: dict[str, Any] | None = None,
    company_id: str = "default",
) -> RunRow:
    ensure_company(session, company_id)
    run = RunRow(
        id=str(uuid4()),
        company_id=company_id,
        title=title,
        status="queued",
        objectives=objectives,
        workspace_ids=workspace_ids,
        plan=plan or [],
        signal=signal or {},
        temporal_workflow_id="",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(run)
    session.flush()
    append_audit(session, run_id=run.id, kind="queued", label="Run created")
    return run


def set_run_workflow(session: Session, run_id: str, workflow_id: str) -> None:
    run = session.get(RunRow, run_id)
    if not run:
        raise KeyError(run_id)
    run.temporal_workflow_id = workflow_id
    run.status = "running"
    run.updated_at = _utcnow()
    append_audit(
        session,
        run_id=run_id,
        kind="started",
        label=f"Temporal workflow {workflow_id}",
        meta={"workflow_id": workflow_id},
    )


def update_run_status(session: Session, run_id: str, status: str) -> None:
    run = session.get(RunRow, run_id)
    if not run:
        raise KeyError(run_id)
    run.status = status
    run.updated_at = _utcnow()
    append_audit(session, run_id=run_id, kind="completed" if status == "succeeded" else status, label=f"Run {status}")


def create_job(
    session: Session,
    *,
    run_id: str,
    workspace_id: str,
    job_type: str,
    agent_id: str,
    requested_action: dict[str, Any],
    idempotency_key: str,
    title: str = "",
) -> JobRow:
    existing = session.scalar(select(JobRow).where(JobRow.idempotency_key == idempotency_key))
    if existing:
        return existing
    job = JobRow(
        id=str(uuid4()),
        run_id=run_id,
        workspace_id=workspace_id,
        agent_id=agent_id,
        job_type=job_type,
        title=title or job_type,
        status="queued",
        requested_action=requested_action,
        idempotency_key=idempotency_key,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(job)
    session.flush()
    append_audit(
        session,
        run_id=run_id,
        job_id=job.id,
        kind="queued",
        label=f"Job queued: {job_type}",
        meta={"job_type": job_type},
    )
    return job


def transition_job(
    session: Session,
    job_id: str,
    status: str,
    *,
    error: str | None = None,
    evidence: dict[str, Any] | None = None,
    approval_id: str | None = None,
    validation_id: str | None = None,
) -> JobRow:
    job = session.get(JobRow, job_id)
    if not job:
        raise KeyError(job_id)
    job.status = status
    job.updated_at = _utcnow()
    if status == "running" and job.started_at is None:
        job.started_at = _utcnow()
    if status in ("succeeded", "failed"):
        job.finished_at = _utcnow()
    if error is not None:
        job.error = error
    if evidence is not None:
        job.evidence = evidence
    if approval_id is not None:
        job.approval_id = approval_id
    if validation_id is not None:
        job.validation_id = validation_id

    kind_map = {
        "running": "started",
        "succeeded": "completed",
        "failed": "failed",
        "blocked_for_approval": "approval",
        "queued": "queued",
    }
    append_audit(
        session,
        run_id=job.run_id,
        job_id=job.id,
        kind=kind_map.get(status, status),
        label=f"Job {status}: {job.job_type}",
        meta={"status": status, **({"error": error} if error else {})},
    )
    return job


def create_approval(
    session: Session,
    *,
    job: JobRow,
    temporal_workflow_id: str,
    intent_summary: str,
    diff_preview: dict[str, Any] | None = None,
) -> ApprovalRow:
    appr = ApprovalRow(
        job_id=job.id,
        run_id=job.run_id,
        workspace_id=job.workspace_id,
        agent_id=job.agent_id,
        job_type=job.job_type,
        title=job.title,
        intent_summary=intent_summary,
        diff_preview=diff_preview or {"before": "", "after": str(job.requested_action)},
        decision="pending",
        temporal_workflow_id=temporal_workflow_id,
        created_at=_utcnow(),
    )
    session.add(appr)
    session.flush()
    job.approval_id = appr.id
    job.status = "blocked_for_approval"
    job.updated_at = _utcnow()
    append_audit(
        session,
        run_id=job.run_id,
        job_id=job.id,
        kind="approval",
        label="Blocked for human approval",
        meta={"approval_id": appr.id},
    )
    return appr


def decide_approval(
    session: Session,
    approval_id: str,
    decision: str,
    edited_payload: str | None = None,
) -> ApprovalRow:
    appr = session.get(ApprovalRow, approval_id)
    if not appr:
        raise KeyError(approval_id)
    if appr.decision != "pending":
        return appr
    appr.decision = decision
    appr.decided_at = _utcnow()
    if edited_payload is not None:
        appr.edited_payload = edited_payload
        preview = dict(appr.diff_preview or {})
        preview["after"] = edited_payload
        appr.diff_preview = preview
    append_audit(
        session,
        run_id=appr.run_id,
        job_id=appr.job_id,
        kind="approval",
        label=f"Approval {decision}",
        meta={"approval_id": approval_id, "decision": decision},
    )
    return appr


def create_validation(
    session: Session,
    *,
    job: JobRow,
    verdict: str,
    message: str,
    reasoning: str,
    checks: list[dict[str, Any]],
    confidence: float,
    evidence: dict[str, Any] | None,
) -> ValidationRow:
    row = ValidationRow(
        job_id=job.id,
        run_id=job.run_id,
        workspace_id=job.workspace_id,
        agent_id=job.agent_id,
        job_type=job.job_type,
        verdict=verdict,
        confidence=confidence,
        message=message,
        reasoning=reasoning,
        checks=checks,
        evidence=evidence,
        checked_at=_utcnow(),
    )
    session.add(row)
    session.flush()
    job.validation_id = row.id
    append_audit(
        session,
        run_id=job.run_id,
        job_id=job.id,
        kind="validation",
        label=f"Validation {verdict}",
        meta={"verdict": verdict, "validation_id": row.id},
    )
    return row


# --- Read / API aggregate ---


def list_workspaces_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(WorkspaceRow).order_by(WorkspaceRow.created_at)).all()
    return [workspace_to_api(r) for r in rows]


def list_runs_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(RunRow).options(selectinload(RunRow.jobs)).order_by(RunRow.created_at.desc())
    ).all()
    return [run_to_api(r) for r in rows]


def get_run_api(session: Session, run_id: str) -> dict[str, Any] | None:
    row = session.scalar(
        select(RunRow).options(selectinload(RunRow.jobs)).where(RunRow.id == run_id)
    )
    return run_to_api(row) if row else None


def list_jobs_api(session: Session, run_id: str | None = None) -> list[dict[str, Any]]:
    q = select(JobRow).order_by(JobRow.created_at.desc())
    if run_id:
        q = q.where(JobRow.run_id == run_id)
    return [job_to_api(r) for r in session.scalars(q).all()]


def list_timeline_api(session: Session, run_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(AuditEventRow).where(AuditEventRow.run_id == run_id).order_by(AuditEventRow.at)
    ).all()
    return [timeline_to_api(r) for r in rows]


def list_approvals_api(session: Session, decision: str | None = None) -> list[dict[str, Any]]:
    from aip.approvals.preview import build_approval_preview

    q = select(ApprovalRow).order_by(ApprovalRow.created_at.desc())
    if decision:
        q = q.where(ApprovalRow.decision == decision)
    out: list[dict[str, Any]] = []
    for row in session.scalars(q).all():
        diff = dict(row.diff_preview or {})
        if not isinstance(diff.get("context"), dict):
            job = session.get(JobRow, row.job_id)
            run = session.get(RunRow, row.run_id) if row.run_id else None
            agent = session.get(AgentRow, row.agent_id) if row.agent_id else None
            if job:
                enriched = build_approval_preview(
                    job_type=job.job_type,
                    requested_action=dict(job.requested_action or {}),
                    job_title=str(job.title or row.title or ""),
                    policy_reason=str(row.intent_summary or ""),
                    run_signal=run.signal if run and isinstance(run.signal, dict) else {},
                    agent_name=str(agent.name or "") if agent else "",
                )
                diff = {**diff, **enriched}
        payload = approval_to_api(row)
        if diff.get("context"):
            payload["context"] = diff["context"]
            payload["diffPreview"] = diff
        out.append(payload)
    return out


def list_validations_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(ValidationRow).order_by(ValidationRow.checked_at.desc())).all()
    return [validation_to_api(r) for r in rows]


def list_agents_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(AgentRow).options(selectinload(AgentRow.guardrails)).order_by(AgentRow.created_at)
    ).all()
    return [agent_to_api(r) for r in rows]


def get_agent_api(session: Session, agent_id: str) -> dict[str, Any] | None:
    row = session.scalar(
        select(AgentRow).options(selectinload(AgentRow.guardrails)).where(AgentRow.id == agent_id)
    )
    return agent_to_api(row) if row else None


def list_policies_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(PolicyRow).order_by(PolicyRow.workspace_id, PolicyRow.action)).all()
    by_ws: dict[str, list[PolicyRow]] = {}
    for r in rows:
        by_ws.setdefault(r.workspace_id, []).append(r)
    return [policy_group_to_api(ws, items) for ws, items in by_ws.items()]


def list_context_api(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ContextDocumentRow).order_by(ContextDocumentRow.created_at.desc())
    ).all()
    return [context_to_api(r) for r in rows]


def get_company_name(session: Session) -> str:
    row = session.get(CompanyRow, "default")
    return row.name if row else ""


OPS_TABLES_TRUNCATE = (
    "audit_events, validations, approvals, jobs, runs, "
    "agent_guardrails, agents, policies, context_documents, workspaces, integration_calls"
)


def record_integration_call(
    session: Session,
    *,
    system: str,
    ok: bool,
    error: str | None = None,
    latency_ms: int | None = None,
) -> IntegrationCallRow:
    """Upsert lastSuccessfulCallAt / lastError for Integrations page honesty."""
    name = (system or "").strip().lower()
    if not name:
        raise ValueError("system required")
    row = session.get(IntegrationCallRow, name)
    if row is None:
        row = IntegrationCallRow(name=name)
        session.add(row)
    now = _utcnow()
    row.updated_at = now
    if latency_ms is not None:
        row.last_latency_ms = int(latency_ms)
    if ok:
        row.last_successful_call_at = now
        row.last_error = None
        row.success_count = int(row.success_count or 0) + 1
    else:
        row.last_error = (error or "error")[:1000]
        row.last_error_at = now
        row.error_count = int(row.error_count or 0) + 1
    session.flush()
    return row


def get_integration_call_stats(session: Session) -> dict[str, dict[str, Any]]:
    rows = session.scalars(select(IntegrationCallRow)).all()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out[row.name] = {
            "lastSuccessfulCallAt": row.last_successful_call_at.isoformat()
            if row.last_successful_call_at
            else None,
            "lastError": row.last_error,
            "lastErrorAt": row.last_error_at.isoformat() if row.last_error_at else None,
            "latencyMsP50": row.last_latency_ms,
            "successCount": row.success_count,
            "errorCount": row.error_count,
        }
    return out


def clear_all_ops_data(session: Session) -> dict[str, int]:
    """Wipe console operational data (workspaces, agents, runs, …). Keeps companies row."""
    from sqlalchemy import text

    session.execute(text(f"TRUNCATE {OPS_TABLES_TRUNCATE} RESTART IDENTITY CASCADE"))
    company = session.get(CompanyRow, "default")
    if company is not None:
        company.name = ""
    return {"cleared": 1}


def build_demo_state(session: Session, integrations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Aggregate payload matching frontend DemoState / HttpAdapter.getState()."""
    return {
        "companyName": get_company_name(session),
        "contextDocuments": list_context_api(session),
        "workspaces": list_workspaces_api(session),
        "runs": list_runs_api(session),
        "jobs": list_jobs_api(session),
        "timeline": [
            timeline_to_api(e)
            for e in session.scalars(select(AuditEventRow).order_by(AuditEventRow.at.desc()).limit(500)).all()
        ],
        "approvals": list_approvals_api(session),
        "policies": list_policies_api(session),
        "integrations": integrations or [],
        "validations": list_validations_api(session),
        "agents": list_agents_api(session),
    }

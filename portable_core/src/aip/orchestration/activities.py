"""Temporal activities — DB + connectors (never long writes in FastAPI handlers)."""

from __future__ import annotations

from typing import Any

from temporalio import activity

from aip.db.repo import (
    append_audit,
    create_approval,
    create_job,
    create_validation,
    decide_approval,
    list_agents_api,
    transition_job,
    update_run_status,
)
from aip.db.schema import init_db
from aip.db.serializers import agent_to_api, approval_to_api, job_to_api, workspace_to_api
from aip.db.session import session_scope
from aip.director.auditor import audit_routing
from aip.director.router import route
from aip.jobs.idempotency import make_idempotency_key
from aip.jobs.validate import validate_job
from aip.kg.persist import ingest_context
from aip.policy.engine import evaluate_job_policy
from aip.runtime.agents_sdk import execute_job_via_agents_runtime


@activity.defn(name="ensure_schema")
async def ensure_schema() -> dict[str, Any]:
    init_db()
    return {"ok": True}


@activity.defn(name="ingest_kg_activity")
async def ingest_kg_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        result = ingest_context(
            session,
            raw=payload["raw"],
            source=payload.get("source") or "paste",
            name=payload.get("name"),
        )
        return result


@activity.defn(name="director_route_activity")
async def director_route_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """General catalog routing + routing auditor."""
    init_db()
    with session_scope() as session:
        from aip.db.orm import AgentRow, WorkspaceRow
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select

        ws = session.get(WorkspaceRow, payload["workspace_id"])
        if not ws:
            return {"ok": False, "error": "workspace not found", "accepted": [], "rejected": [], "notes": []}
        agents = list_agents_api(session)
        # Filter to agents that include this workspace (or Validation)
        agents_ws = [
            a
            for a in agents
            if payload["workspace_id"] in (a.get("workspaceIds") or [])
            or a.get("role") == "ValidationAgent"
        ]
        workspace = workspace_to_api(ws)
        decision = route(
            agents=agents_ws,
            workspace=workspace,
            objectives=list(payload.get("objectives") or []),
            plan=list(payload.get("plan") or []),
            signal=dict(payload.get("signal") or {}),
        )
        audited = audit_routing(decision, agents=agents_ws, workspace=workspace)

        materialized = []
        run_id = payload["run_id"]
        for pj in audited.accepted:
            key = make_idempotency_key(
                run_id=run_id,
                workspace_id=payload["workspace_id"],
                job_type=pj.job_type,
                requested_action=pj.requested_action,
            )
            job = create_job(
                session,
                run_id=run_id,
                workspace_id=payload["workspace_id"],
                job_type=pj.job_type,
                agent_id=pj.agent_id,
                requested_action=pj.requested_action,
                idempotency_key=key,
                title=pj.title or pj.job_type,
            )
            materialized.append(job_to_api(job))

        append_audit(
            session,
            run_id=run_id,
            kind="started",
            label=f"Director routed {len(materialized)} jobs "
            f"(rejected {len(audited.rejected)})",
            meta={"notes": decision.notes[:20]},
        )
        return {
            "ok": True,
            "jobs": materialized,
            "rejected": [
                {"job_type": j.job_type, "reason": reason, "agent_id": j.agent_id}
                for j, reason in audited.rejected
            ],
            "notes": decision.notes,
        }


@activity.defn(name="evaluate_policy_activity")
async def evaluate_policy_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"decision": "deny", "reason": "job not found"}
        ev = evaluate_job_policy(
            session,
            workspace_id=job.workspace_id,
            agent_id=job.agent_id,
            job_type=job.job_type,
        )
        return {"decision": ev.decision, "reason": ev.reason, "job_id": job.id}


@activity.defn(name="create_hil_approval_activity")
async def create_hil_approval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"ok": False, "error": "job not found"}
        appr = create_approval(
            session,
            job=job,
            temporal_workflow_id=payload.get("temporal_workflow_id") or "",
            intent_summary=payload.get("intent_summary")
            or f"Approve {job.job_type}: {job.requested_action}",
            diff_preview={
                "before": "",
                "after": str(job.requested_action),
            },
        )
        return {"ok": True, "approval": approval_to_api(appr)}


@activity.defn(name="execute_job_activity")
async def execute_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Real connector writes — GitHub / Gmail / Calendar / optional Jira."""
    init_db()
    job_id = payload["job_id"]
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, job_id)
        if not job:
            return {"ok": False, "error": "job not found"}
        job_type = job.job_type
        agent_id = job.agent_id
        action = dict(job.requested_action or {})
        if payload.get("edited_action") and isinstance(payload["edited_action"], dict):
            action.update(payload["edited_action"])
        transition_job(session, job_id, "running")

    from aip.db.rate_limit import check_rate_limit
    from aip.evidence.contracts import JOB_TYPE_SYSTEM

    system = JOB_TYPE_SYSTEM.get(job_type, "unknown")
    rl = check_rate_limit(key=f"integration:{system}", limit=20, window_sec=60)
    if not rl.get("ok"):
        with session_scope() as session:
            transition_job(session, job_id, "failed", error=str(rl.get("error")))
        return {"ok": False, "error": rl.get("error")}

    result = execute_job_via_agents_runtime(
        job_type,
        action,
        agent_role=str(payload.get("agent_role") or "SpecialistAgent"),
    )

    with session_scope() as session:
        from datetime import datetime, timezone

        from aip.db.orm import AgentRow, JobRow

        if result.get("ok"):
            transition_job(
                session,
                job_id,
                "succeeded",
                evidence=result.get("evidence"),
            )
            agent = session.get(AgentRow, agent_id)
            if agent:
                agent.last_active_at = datetime.now(timezone.utc)
                agent.status = "active"
        else:
            transition_job(
                session,
                job_id,
                "failed",
                error=str(result.get("error"))[:1000],
                evidence=result.get("evidence"),
            )
        job_row = session.get(JobRow, job_id)
        return {
            "ok": bool(result.get("ok")),
            "job": job_to_api(job_row) if job_row else None,
            "error": result.get("error"),
            "evidence": result.get("evidence"),
        }


@activity.defn(name="validate_job_activity")
async def validate_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"ok": False, "error": "job not found"}
        outcome = validate_job(
            job_type=job.job_type,
            evidence=job.evidence,
            requested_action=job.requested_action,
        )
        row = create_validation(
            session,
            job=job,
            verdict=outcome["verdict"],
            message=outcome["message"],
            reasoning=outcome["reasoning"],
            checks=outcome["checks"],
            confidence=float(outcome.get("confidence") or 0),
            evidence=outcome.get("evidence"),
        )
        from aip.db.serializers import validation_to_api

        return {"ok": True, "validation": validation_to_api(row)}


@activity.defn(name="mark_run_status_activity")
async def mark_run_status_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        update_run_status(session, payload["run_id"], payload["status"])
        return {"ok": True}


@activity.defn(name="fail_job_activity")
async def fail_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        transition_job(session, payload["job_id"], "failed", error=payload.get("error") or "denied")
        return {"ok": True}

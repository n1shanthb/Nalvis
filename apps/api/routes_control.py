"""Control-plane REST routes for ops console (HttpAdapter contract)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aip.connectors import smoke as connector_smoke
from aip.db.orm import AgentGuardrailRow, AgentRow, ApprovalRow, PolicyRow, RunRow
from aip.db.repo import (
    build_demo_state,
    clear_all_ops_data,
    create_run,
    decide_approval,
    get_agent_api,
    get_run_api,
    list_agents_api,
    list_approvals_api,
    list_jobs_api,
    list_policies_api,
    list_runs_api,
    list_timeline_api,
    list_validations_api,
    list_workspaces_api,
    set_run_workflow,
)
from aip.db.schema import init_db
from aip.db.serializers import agent_to_api, approval_to_api, guardrail_to_api
from aip.db.session import session_scope
from aip.kg.persist import ingest_context

router = APIRouter(prefix="/api")


class IngestBody(BaseModel):
    raw: str
    source: str = "paste"
    name: str | None = None


class StartRunBody(BaseModel):
    title: str = ""
    objectives: list[str] = Field(default_factory=list)
    workspace_ids: list[str] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    signal: dict[str, Any] = Field(default_factory=dict)
    # If true, also pass raw_kg into workflow (normally ingest is separate)
    raw_kg: str | None = None


class DecideBody(BaseModel):
    decision: str
    editedPayload: str | None = None


class PolicyPatch(BaseModel):
    allowed: bool | None = None
    hilRequired: bool | None = None
    autoMerge: bool | None = None


class GuardrailBody(BaseModel):
    tool: str
    mode: str = "allow"
    label: str | None = None
    rationale: str | None = None


class GuardrailPatch(BaseModel):
    mode: str | None = None
    label: str | None = None
    rationale: str | None = None
    tool: str | None = None


def _init() -> None:
    init_db()


@router.get("/demo/state")
def get_state() -> dict[str, Any]:
    _init()
    integrations = connector_smoke.integrations_console_payload().get("integrations") or []
    with session_scope() as session:
        return build_demo_state(session, integrations=integrations)


@router.delete("/demo/state")
def clear_state() -> dict[str, Any]:
    """Clear all console operational data (workspaces, agents, runs, validations, …)."""
    _init()
    with session_scope() as session:
        clear_all_ops_data(session)
    integrations = connector_smoke.integrations_console_payload().get("integrations") or []
    with session_scope() as session:
        return build_demo_state(session, integrations=integrations)


@router.get("/llm/status")
def llm_status() -> dict[str, Any]:
    """Whether Director/synthesizer can use LLM (OpenAI or OpenRouter). No secrets."""
    from aip.llm.client import llm_configured, resolve_llm_base_url, resolve_llm_model

    return {
        "configured": llm_configured(),
        "baseUrlSet": bool(resolve_llm_base_url()),
        "model": resolve_llm_model(),
        "note": "Start run with empty plan[] uses Director LLM routing when configured.",
    }


@router.post("/context/ingest")
def context_ingest(body: IngestBody) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        result = ingest_context(session, raw=body.raw, source=body.source, name=body.name)
        return result["document"]


@router.get("/workspaces")
def workspaces() -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_workspaces_api(session)


@router.get("/runs")
def runs() -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_runs_api(session)


@router.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        row = get_run_api(session, run_id)
        if not row:
            raise HTTPException(404, "run not found")
        return row


@router.get("/runs/{run_id}/timeline")
def run_timeline(run_id: str) -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_timeline_api(session, run_id)


@router.post("/runs")
async def start_run(body: StartRunBody) -> dict[str, Any]:
    """Create run row + start CompanyRunWorkflow (writes happen in Temporal activities)."""
    _init()
    with session_scope() as session:
        ws_ids = list(body.workspace_ids)
        if not ws_ids:
            ws_ids = [w["id"] for w in list_workspaces_api(session)]
        if not ws_ids:
            raise HTTPException(400, "No workspaces — ingest KG first")
        title = body.title or (body.objectives[0] if body.objectives else "Company run")
        run = create_run(
            session,
            title=title,
            objectives=body.objectives,
            workspace_ids=ws_ids,
            plan=body.plan,
            signal=body.signal,
        )
        run_id = run.id
        plan = list(body.plan)
        signal = dict(body.signal)
        objectives = list(body.objectives)
        raw_kg = body.raw_kg

    workflow_id = f"company-run-{run_id}"
    try:
        from temporalio.client import Client

        from aip.config import settings
        from aip.orchestration.workflows import CompanyRunWorkflow

        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        await client.start_workflow(
            CompanyRunWorkflow.run,
            {
                "run_id": run_id,
                "workspace_ids": ws_ids,
                "objectives": objectives,
                "plan": plan,
                "signal": signal,
                "raw_kg": raw_kg,
            },
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as exc:  # noqa: BLE001
        with session_scope() as session:
            r = session.get(RunRow, run_id)
            if r:
                r.status = "failed"
        raise HTTPException(503, f"Failed to start Temporal workflow: {exc}") from exc

    with session_scope() as session:
        set_run_workflow(session, run_id, workflow_id)
        row = get_run_api(session, run_id)
        return row or {"id": run_id, "temporalWorkflowId": workflow_id}


@router.get("/jobs")
def jobs(run_id: str | None = None) -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_jobs_api(session, run_id=run_id)


@router.get("/approvals")
def approvals(decision: str | None = None) -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_approvals_api(session, decision=decision)


@router.post("/approvals/{approval_id}/decide")
async def approval_decide(approval_id: str, body: DecideBody) -> dict[str, Any]:
    _init()
    if body.decision not in ("approved", "denied", "edited"):
        raise HTTPException(400, "decision must be approved|denied|edited")

    with session_scope() as session:
        try:
            appr = decide_approval(session, approval_id, body.decision, body.editedPayload)
        except KeyError as exc:
            raise HTTPException(404, "approval not found") from exc
        wf_id = appr.temporal_workflow_id
        payload = approval_to_api(appr)

    if wf_id:
        try:
            from temporalio.client import Client

            from aip.config import settings

            client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
            handle = client.get_workflow_handle(wf_id)
            await handle.signal(
                "approval_decision",
                {
                    "decision": body.decision,
                    "editedPayload": body.editedPayload,
                    "approval_id": approval_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f"Approval saved but Temporal signal failed: {exc}") from exc

    return payload


@router.get("/policies")
def policies() -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_policies_api(session)


@router.patch("/policies/{workspace_id}/{action}")
def policy_patch(workspace_id: str, action: str, body: PolicyPatch) -> dict[str, Any]:
    _init()
    from sqlalchemy import select

    with session_scope() as session:
        row = session.scalar(
            select(PolicyRow).where(
                PolicyRow.workspace_id == workspace_id,
                PolicyRow.action == action,
            )
        )
        if not row:
            raise HTTPException(404, "policy not found")
        if body.allowed is not None:
            row.allowed = body.allowed
        if body.hilRequired is not None:
            row.hil_required = body.hilRequired
        if body.autoMerge is not None:
            row.auto_merge = body.autoMerge
        session.flush()
        from aip.db.serializers import policy_group_to_api

        rows = session.scalars(select(PolicyRow).where(PolicyRow.workspace_id == workspace_id)).all()
        return policy_group_to_api(workspace_id, list(rows))


@router.get("/validations")
def validations() -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_validations_api(session)


@router.get("/agents")
def agents() -> list[dict[str, Any]]:
    _init()
    with session_scope() as session:
        return list_agents_api(session)


@router.get("/agents/{agent_id}")
def agent_detail(agent_id: str) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        row = get_agent_api(session, agent_id)
        if not row:
            raise HTTPException(404, "agent not found")
        return row


@router.get("/agents/{agent_id}/metrics")
def agent_metrics(agent_id: str) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        validations = list_validations_api(session)
        jobs = list_jobs_api(session)
        agent_validations = [v for v in validations if v.get("agentId") == agent_id]
        overall = {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0}
        by_job: dict[str, dict[str, int]] = {}
        by_ws: dict[str, dict[str, int]] = {}
        for v in agent_validations:
            verdict = v.get("verdict") or "NO_EVIDENCE"
            overall[verdict] = overall.get(verdict, 0) + 1
            jt = v.get("jobType") or ""
            by_job.setdefault(jt, {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0})
            by_job[jt][verdict] = by_job[jt].get(verdict, 0) + 1
            ws = v.get("workspaceId") or ""
            by_ws.setdefault(ws, {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0})
            by_ws[ws][verdict] = by_ws[ws].get(verdict, 0) + 1
        agent_jobs = [j for j in jobs if j.get("agentId") == agent_id]
        type_counts: dict[str, int] = {}
        for j in agent_jobs:
            type_counts[j["jobType"]] = type_counts.get(j["jobType"], 0) + 1
        common = sorted(type_counts, key=lambda k: -type_counts[k])[:5]
        return {
            "agentId": agent_id,
            "overall": overall,
            "byJobType": by_job,
            "byWorkspace": by_ws,
            "totalJobs": len(agent_jobs),
            "commonJobTypes": common,
        }


@router.post("/agents/{agent_id}/guardrails")
def add_guardrail(agent_id: str, body: GuardrailBody) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        agent = session.get(AgentRow, agent_id)
        if not agent:
            raise HTTPException(404, "agent not found")
        gr = AgentGuardrailRow(
            id=f"gr-{uuid4().hex[:12]}",
            agent_id=agent_id,
            tool=body.tool,
            mode=body.mode,
            label=body.label or body.tool,
            rationale=body.rationale or "",
            source="user",
        )
        session.add(gr)
        session.flush()
        return guardrail_to_api(gr)


@router.patch("/agents/{agent_id}/guardrails/{guardrail_id}")
def patch_guardrail(agent_id: str, guardrail_id: str, body: GuardrailPatch) -> dict[str, Any]:
    _init()
    with session_scope() as session:
        gr = session.get(AgentGuardrailRow, guardrail_id)
        if not gr or gr.agent_id != agent_id:
            raise HTTPException(404, "guardrail not found")
        if body.mode is not None:
            gr.mode = body.mode
        if body.label is not None:
            gr.label = body.label
        if body.rationale is not None:
            gr.rationale = body.rationale
        if body.tool is not None:
            gr.tool = body.tool
        session.flush()
        return guardrail_to_api(gr)


@router.delete("/agents/{agent_id}/guardrails/{guardrail_id}")
def delete_guardrail(agent_id: str, guardrail_id: str) -> bool:
    _init()
    with session_scope() as session:
        gr = session.get(AgentGuardrailRow, guardrail_id)
        if not gr or gr.agent_id != agent_id:
            raise HTTPException(404, "guardrail not found")
        session.delete(gr)
        return True

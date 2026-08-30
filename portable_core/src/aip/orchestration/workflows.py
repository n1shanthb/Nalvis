"""Temporal workflows — CompanyRun / ProductRun / Validation (Authority names).

Activities are referenced by *name* so the workflow sandbox never imports
SQLAlchemy / connectors.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


_ACT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=5,
)

_WRITE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=90),
    maximum_attempts=3,
)


@workflow.defn(name="ValidationWorkflow")
class ValidationWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_ids = list(payload.get("job_ids") or [])
        results = []
        for job_id in job_ids:
            res = await workflow.execute_activity(
                "validate_job_activity",
                {"job_id": job_id},
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=_ACT_RETRY,
            )
            results.append(res)
        return {"ok": True, "results": results}


@workflow.defn(name="ProductRunWorkflow")
class ProductRunWorkflow:
    def __init__(self) -> None:
        self._approval_decision: dict[str, Any] | None = None

    @workflow.signal(name="approval_decision")
    def approval_decision(self, payload: dict[str, Any]) -> None:
        self._approval_decision = payload

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await workflow.execute_activity(
            "ensure_schema",
            start_to_close_timeout=timedelta(seconds=30),
        )

        routed = await workflow.execute_activity(
            "director_route_activity",
            {
                "run_id": payload["run_id"],
                "workspace_id": payload["workspace_id"],
                "objectives": payload.get("objectives") or [],
                "plan": payload.get("plan") or [],
                "signal": payload.get("signal") or {},
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACT_RETRY,
        )

        job_results: list[dict[str, Any]] = []
        executed_job_ids: list[str] = []

        for job in routed.get("jobs") or []:
            job_id = job["id"]
            policy = await workflow.execute_activity(
                "evaluate_policy_activity",
                {"job_id": job_id},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_ACT_RETRY,
            )
            decision = policy.get("decision")
            if decision == "deny":
                await workflow.execute_activity(
                    "fail_job_activity",
                    {"job_id": job_id, "error": policy.get("reason") or "policy deny"},
                    start_to_close_timeout=timedelta(seconds=30),
                )
                job_results.append({"job_id": job_id, "status": "failed", "reason": "deny"})
                continue

            edited_action = None
            if decision == "hil":
                self._approval_decision = None
                await workflow.execute_activity(
                    "create_hil_approval_activity",
                    {
                        "job_id": job_id,
                        "temporal_workflow_id": workflow.info().workflow_id,
                        "intent_summary": policy.get("reason"),
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                await workflow.wait_condition(lambda: self._approval_decision is not None)
                assert self._approval_decision is not None
                dec = self._approval_decision.get("decision")
                if dec == "denied":
                    await workflow.execute_activity(
                        "fail_job_activity",
                        {"job_id": job_id, "error": "Denied by human approver"},
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    job_results.append({"job_id": job_id, "status": "failed", "reason": "denied"})
                    continue
                if dec not in ("approved", "edited"):
                    await workflow.execute_activity(
                        "fail_job_activity",
                        {"job_id": job_id, "error": f"Unexpected approval decision: {dec}"},
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    job_results.append({"job_id": job_id, "status": "failed", "reason": "bad_decision"})
                    continue
                if self._approval_decision.get("editedPayload"):
                    edited_action = {"body": self._approval_decision["editedPayload"]}

            exec_res = await workflow.execute_activity(
                "execute_job_activity",
                {"job_id": job_id, "edited_action": edited_action},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_WRITE_RETRY,
            )
            job_results.append(exec_res)
            executed_job_ids.append(job_id)

        for jid in executed_job_ids:
            await workflow.execute_activity(
                "validate_job_activity",
                {"job_id": jid},
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=_ACT_RETRY,
            )

        succeeded_job_ids = [jr.get("job_id") for jr in job_results if jr.get("ok")]

        return {
            "ok": True,
            "workspace_id": payload["workspace_id"],
            "routed": routed,
            "job_results": job_results,
            "succeeded_job_ids": succeeded_job_ids,
            "executed_job_ids": executed_job_ids,
        }


@workflow.defn(name="CompanyRunWorkflow")
class CompanyRunWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await workflow.execute_activity(
            "ensure_schema",
            start_to_close_timeout=timedelta(seconds=30),
        )

        run_id = payload["run_id"]
        wf_id = workflow.info().workflow_id

        if payload.get("raw_kg"):
            await workflow.execute_activity(
                "ingest_kg_activity",
                {
                    "raw": payload["raw_kg"],
                    "source": payload.get("source") or "paste",
                    "name": payload.get("kg_name"),
                },
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=_ACT_RETRY,
            )

        workspace_ids = list(payload.get("workspace_ids") or [])
        child_results = []
        for ws_id in workspace_ids:
            child = await workflow.execute_child_workflow(
                ProductRunWorkflow.run,
                {
                    "run_id": run_id,
                    "workspace_id": ws_id,
                    "objectives": payload.get("objectives") or [],
                    "plan": payload.get("plan") or [],
                    "signal": payload.get("signal") or {},
                    "temporal_workflow_id": wf_id,
                },
                id=f"{wf_id}:product:{ws_id}",
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            child_results.append(child)

        any_fail = False
        any_ok = False
        for cr in child_results:
            for jr in cr.get("job_results") or []:
                if jr.get("ok") or jr.get("status") == "succeeded":
                    any_ok = True
                if jr.get("ok") is False or jr.get("status") == "failed":
                    any_fail = True
        if any_ok and any_fail:
            status = "partial"
        elif any_ok:
            status = "succeeded"
        elif any_fail:
            status = "failed"
        else:
            status = "succeeded" if not workspace_ids else "failed"

        await workflow.execute_activity(
            "mark_run_status_activity",
            {"run_id": run_id, "status": status},
            start_to_close_timeout=timedelta(seconds=30),
        )
        return {"ok": True, "status": status, "children": child_results}


@workflow.defn(name="GmailInboundWorkflow")
class GmailInboundWorkflow:
    """Thin durable path: fetch Gmail facts → start CompanyRun with Director signal."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await workflow.execute_activity(
            "ensure_schema",
            start_to_close_timeout=timedelta(seconds=30),
        )
        fetched = await workflow.execute_activity(
            "fetch_gmail_inbound_signal_activity",
            {
                "history_id": payload.get("history_id") or "",
                "message_id": payload.get("message_id") or "",
                "delivery_id": payload.get("delivery_id") or "",
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACT_RETRY,
        )
        if not fetched.get("ok"):
            return {"ok": False, "error": fetched.get("error"), "fetched": fetched}
        if fetched.get("skipped"):
            return {"ok": True, "skipped": True, "fetched": fetched}

        started = await workflow.execute_activity(
            "start_company_run_from_signal_activity",
            {
                "signal": fetched.get("signal") or {},
                "workspace_ids": payload.get("workspace_ids") or [],
                "objectives": payload.get("objectives") or [],
                "title": payload.get("title"),
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACT_RETRY,
        )
        return {"ok": bool(started.get("ok")), "fetched": fetched, "started": started}


@workflow.defn(name="GithubInboundWorkflow")
class GithubInboundWorkflow:
    """Thin durable path: normalize GitHub webhook → CompanyRun with Director signal."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await workflow.execute_activity(
            "ensure_schema",
            start_to_close_timeout=timedelta(seconds=30),
        )
        normalized = await workflow.execute_activity(
            "normalize_github_webhook_signal_activity",
            {
                "event": payload.get("event") or "",
                "action": payload.get("action") or "",
                "delivery_id": payload.get("delivery_id") or "",
                "payload": payload.get("payload") or {},
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=_ACT_RETRY,
        )
        if not normalized.get("ok"):
            return {"ok": False, "error": "normalize_failed", "normalized": normalized}

        started = await workflow.execute_activity(
            "start_company_run_from_signal_activity",
            {
                "signal": normalized.get("signal") or {},
                "workspace_ids": payload.get("workspace_ids") or [],
                "objectives": normalized.get("objectives") or [],
                "title": (normalized.get("signal") or {}).get("subject"),
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACT_RETRY,
        )
        return {"ok": bool(started.get("ok")), "normalized": normalized, "started": started}

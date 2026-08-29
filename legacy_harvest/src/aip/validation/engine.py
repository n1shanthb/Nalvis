"""Validation orchestration."""

from __future__ import annotations

import logging
from typing import Any

from aip.runtime.spec_loader import load_spec
from aip.validation.claims import extract_github_claim, extract_gmail_claim
from aip.validation.evidence import get_evidence, save_run_evidence
from aip.validation.guardrail_bypass import check_guardrail_bypass
from aip.validation.models import CheckMarks, ValidationRecord
from aip.validation.response_watch import sla_mark_for_delivery
from aip.validation.store import ValidationStore
from aip.validation.verify_github import verify_github_comment
from aip.validation.verify_gmail import verify_gmail_send

logger = logging.getLogger(__name__)


def _store() -> ValidationStore:
    from aip.app_context import ctx

    return ctx.validation


def _aggregate_verdict(marks: CheckMarks) -> str:
    if marks.response_sla == "FAIL" or marks.guardrail_bypass == "FAIL" or marks.outcome == "FAIL":
        return "FAIL"
    if marks.outcome == "INSUFFICIENT_EVIDENCE" and marks.response_sla != "FAIL":
        return "INSUFFICIENT_EVIDENCE"
    if marks.outcome == "ERROR":
        return "ERROR"
    if marks.outcome == "PASS" and marks.guardrail_bypass in {"PASS", "NOT_APPLICABLE"}:
        return "PASS"
    return "PARTIAL"


def _confidence_for(marks: CheckMarks) -> float:
    if marks.outcome == "PASS" and marks.guardrail_bypass != "FAIL":
        return 0.92
    if marks.outcome == "FAIL":
        return 0.88
    return 0.65


def validate_after_run(
    *,
    execution_id: str | None,
    spec_id: str,
    project_id: str,
    system: str,
    success: bool,
    output: str,
    error: str | None,
    tool_events: list[dict[str, Any]],
    context: dict[str, Any],
    run_meta: dict[str, Any] | None = None,
    delivery_key: str = "",
    watch_id: str | None = None,
) -> ValidationRecord | None:
    try:
        spec = load_spec(spec_id)
        objective = spec.goal or spec.agent.title or spec_id
        org_id = spec.agent.org_id or project_id
    except Exception:  # noqa: BLE001
        objective = spec_id
        org_id = project_id

    if execution_id:
        save_run_evidence(
            execution_id,
            spec_id=spec_id,
            project_id=org_id,
            system=system,
            objective=objective,
            success=success,
            output=output,
            error=error,
            tool_events=tool_events,
            context=context,
            run_meta=run_meta,
        )

    evidence = get_evidence(execution_id) if execution_id else {
        "spec_id": spec_id,
        "project_id": org_id,
        "system": system,
        "objective": objective,
        "success": success,
        "output": output,
        "error": error or "",
        "tool_events": tool_events,
        "context": context,
        "run_meta": run_meta or {},
        "guardrail_decisions": [],
    }
    meta = {**(evidence.get("run_meta") or {}), **(run_meta or {})}

    marks = CheckMarks(log_ok="PASS" if tool_events or output or error else "FAIL")
    marks.response_sla = sla_mark_for_delivery(delivery_key) if delivery_key else "NOT_APPLICABLE"

    bypass_status, bypass_msg = check_guardrail_bypass(evidence, meta)
    marks.guardrail_bypass = bypass_status  # type: ignore[assignment]

    claimed_action = ""
    expected = ""
    observed = ""
    refs: dict[str, Any] = {"execution_id": execution_id, "delivery_key": delivery_key}

    if system == "github":
        claim = extract_github_claim(evidence, meta)
        if claim:
            claimed_action = "github_comment"
            status, expected, observed, extra = verify_github_comment(claim)
            marks.outcome = status  # type: ignore[assignment]
            refs.update(extra)
            refs["claim"] = claim
        elif success and output.strip():
            marks.outcome = "INSUFFICIENT_EVIDENCE"
            claimed_action = "unspecified_github_action"
            expected = "Verifiable comment claim"
            observed = output[:200]
        else:
            marks.outcome = "NOT_APPLICABLE"
    elif system == "gmail":
        claim = extract_gmail_claim(evidence)
        if claim:
            claimed_action = str(claim.get("tool") or "gmail_send")
            status, expected, observed, extra = verify_gmail_send(claim)
            marks.outcome = status  # type: ignore[assignment]
            refs.update(extra)
            refs["claim"] = claim
        else:
            marks.outcome = "NOT_APPLICABLE" if not success else "INSUFFICIENT_EVIDENCE"
    else:
        marks.outcome = "NOT_APPLICABLE"

    verdict = _aggregate_verdict(marks)
    message_parts = [p for p in [bypass_msg, observed if marks.outcome == "FAIL" else ""] if p]

    record = ValidationRecord(
        execution_id=execution_id,
        watch_id=watch_id,
        spec_id=spec_id,
        project_id=org_id,
        system=system,
        objective=objective,
        verdict=verdict,  # type: ignore[arg-type]
        confidence=_confidence_for(marks),
        claimed_action=claimed_action,
        expected=expected,
        observed=observed,
        check_marks=marks,
        evidence_refs=refs,
        message="; ".join(message_parts)[:500],
    )
    _store().upsert_record(record)
    return record


def validate_execution_id(execution_id: str) -> ValidationRecord | None:
    evidence = get_evidence(execution_id)
    if not evidence:
        from aip.app_context import ctx

        row = ctx.executions.get(execution_id)
        if not row:
            return None
        evidence = {
            "spec_id": row.agent_id,
            "project_id": row.project_id,
            "system": "",
            "objective": "",
            "success": row.status == "COMPLETED",
            "output": "",
            "error": row.failure_reason,
            "tool_events": [],
            "context": {},
            "run_meta": {},
            "guardrail_decisions": [],
        }
    return validate_after_run(
        execution_id=execution_id,
        spec_id=str(evidence.get("spec_id") or ""),
        project_id=str(evidence.get("project_id") or ""),
        system=str(evidence.get("system") or ""),
        success=bool(evidence.get("success")),
        output=str(evidence.get("output") or ""),
        error=str(evidence.get("error") or "") or None,
        tool_events=list(evidence.get("tool_events") or []),
        context=dict(evidence.get("context") or {}),
        run_meta=dict(evidence.get("run_meta") or {}),
        delivery_key=str((evidence.get("run_meta") or {}).get("delivery_key") or ""),
    )


def revalidate_execution(execution_id: str) -> ValidationRecord | None:
    return validate_execution_id(execution_id)

"""Pure validation orchestration (no app_context / DB store)."""

from __future__ import annotations

from typing import Any

from aip.validation.claims import extract_github_claim, extract_gmail_claim
from aip.validation.evidence import get_evidence, save_run_evidence
from aip.validation.guardrail_bypass import check_guardrail_bypass
from aip.validation.models import CheckMarks, ValidationRecord
from aip.validation.verdicts import to_authority_verdict
from aip.validation.verify_github import verify_github_comment
from aip.validation.verify_gmail import verify_gmail_send


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
    objective: str | None = None,
    persist: bool = True,
) -> ValidationRecord:
    """Validate a completed run using injectable evidence + verifiers.

    Unlike the legacy engine, this does not load specs from disk or upsert
    into a DB store. Callers persist ValidationRecord themselves.
    """
    org_id = project_id
    objective_text = objective or spec_id
    meta = dict(run_meta or {})

    if persist and execution_id:
        save_run_evidence(
            execution_id,
            spec_id=spec_id,
            project_id=org_id,
            system=system,
            objective=objective_text,
            success=success,
            output=output,
            error=error,
            tool_events=tool_events,
            context=context,
            run_meta=meta,
        )

    evidence = get_evidence(execution_id) if execution_id else {
        "spec_id": spec_id,
        "project_id": org_id,
        "system": system,
        "objective": objective_text,
        "success": success,
        "output": output,
        "error": error or "",
        "tool_events": tool_events,
        "context": context,
        "run_meta": meta,
        "guardrail_decisions": [],
    }
    meta = {**(evidence.get("run_meta") or {}), **meta}

    marks = CheckMarks(log_ok="PASS" if tool_events or output or error else "FAIL")
    marks.response_sla = "NOT_APPLICABLE"

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

    return ValidationRecord(
        execution_id=execution_id,
        watch_id=watch_id,
        spec_id=spec_id,
        project_id=org_id,
        system=system,
        objective=objective_text,
        verdict=verdict,  # type: ignore[arg-type]
        confidence=_confidence_for(marks),
        claimed_action=claimed_action,
        expected=expected,
        observed=observed,
        check_marks=marks,
        evidence_refs={
            **refs,
            "authority_verdict": to_authority_verdict(verdict),
        },
        message="; ".join(message_parts)[:500],
    )

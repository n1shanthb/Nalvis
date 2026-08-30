"""In-memory evidence store (no app_context / DB)."""

from __future__ import annotations

from typing import Any

_EVIDENCE: dict[str, dict[str, Any]] = {}


def clear_evidence() -> None:
    _EVIDENCE.clear()


def save_run_evidence(
    execution_id: str,
    *,
    spec_id: str,
    project_id: str,
    system: str,
    objective: str,
    success: bool,
    output: str,
    error: str | None,
    tool_events: list[dict[str, Any]],
    context: dict[str, Any],
    run_meta: dict[str, Any] | None = None,
) -> None:
    existing = dict(_EVIDENCE.get(execution_id) or {})
    payload = {
        **existing,
        "spec_id": spec_id,
        "project_id": project_id,
        "system": system,
        "objective": objective,
        "success": success,
        "output": output,
        "error": error or "",
        "tool_events": tool_events,
        "context": context,
        "run_meta": {**(existing.get("run_meta") or {}), **(run_meta or {})},
        "guardrail_decisions": existing.get("guardrail_decisions") or [],
    }
    _EVIDENCE[execution_id] = payload


def append_guardrail_decision(execution_id: str, decision: dict[str, Any]) -> None:
    if not execution_id:
        return
    existing = dict(_EVIDENCE.get(execution_id) or {})
    decisions = list(existing.get("guardrail_decisions") or [])
    decisions.append(decision)
    existing["guardrail_decisions"] = decisions
    _EVIDENCE[execution_id] = existing


def get_evidence(execution_id: str) -> dict[str, Any]:
    return dict(_EVIDENCE.get(execution_id) or {})

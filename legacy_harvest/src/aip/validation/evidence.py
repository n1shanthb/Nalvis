"""Execution evidence persistence for validation."""

from __future__ import annotations

import json
from typing import Any

from aip.app_context import ctx


def _load_evidence(execution_id: str) -> dict[str, Any]:
    row = ctx.executions.get(execution_id)
    if not row or not getattr(row, "evidence_json", None):
        return {}
    try:
        data = json.loads(row.evidence_json or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_evidence(execution_id: str, payload: dict[str, Any]) -> None:
    ctx.executions.save_evidence_json(execution_id, json.dumps(payload))


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
    ctx.executions.ensure_tables()
    existing = _load_evidence(execution_id)
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
    _save_evidence(execution_id, payload)


def append_guardrail_decision(execution_id: str, decision: dict[str, Any]) -> None:
    if not execution_id:
        return
    ctx.executions.ensure_tables()
    existing = _load_evidence(execution_id)
    decisions = list(existing.get("guardrail_decisions") or [])
    decisions.append(decision)
    existing["guardrail_decisions"] = decisions
    _save_evidence(execution_id, existing)


def get_evidence(execution_id: str) -> dict[str, Any]:
    return _load_evidence(execution_id)

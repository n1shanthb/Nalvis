"""Detect effective guardrail bypass."""

from __future__ import annotations

from typing import Any

from aip.validation.claims import GITHUB_WRITE_TOOLS, GMAIL_SEND_TOOLS

WRITE_TOOLS = GITHUB_WRITE_TOOLS | GMAIL_SEND_TOOLS


def _has_consumed_approval(execution_id: str, tool: str) -> bool:
    if not execution_id:
        return False
    try:
        from aip.app_context import ctx
        from aip.guardrails.store import ApprovalStatus

        rows = ctx.approvals.list_for_execution(execution_id)
    except Exception:  # noqa: BLE001
        return False
    for row in rows:
        if str(row.tool or "") != tool:
            continue
        if row.status in {ApprovalStatus.APPROVED, ApprovalStatus.CONSUMED}:
            return True
        # Middleware records an allow decision after successful consume.
    return False


def check_guardrail_bypass(
    evidence: dict[str, Any],
    run_meta: dict[str, Any],
) -> tuple[str, str]:
    if run_meta.get("comment_fallback"):
        return "FAIL", "Comment posted via server fallback outside MCP gateway PEP"

    tool_events = evidence.get("tool_events") or []
    writes = [e for e in tool_events if str(e.get("name") or "") in WRITE_TOOLS]
    if not writes and not run_meta.get("comment_fallback"):
        return "NOT_APPLICABLE", ""

    decisions = evidence.get("guardrail_decisions") or []
    denied_tools = {
        str(d.get("tool") or "")
        for d in decisions
        if str(d.get("decision") or "").lower() in {"deny", "error"}
    }
    for event in writes:
        name = str(event.get("name") or "")
        if name in denied_tools:
            return "FAIL", f"Write tool {name} ran after DENY decision"

    execution_id = str(
        (evidence.get("run_meta") or {}).get("execution_id")
        or run_meta.get("execution_id")
        or evidence.get("execution_id")
        or ""
    )

    # REQUIRE_APPROVAL: write is OK only if approval was consumed / allow recorded.
    require_tools = {
        str(d.get("tool") or "")
        for d in decisions
        if str(d.get("decision") or "").lower() == "require_approval"
    }
    allow_after_approval = {
        str(d.get("tool") or "")
        for d in decisions
        if str(d.get("decision") or "").lower() == "allow"
        and "approval" in str(d.get("reason") or "").lower()
    }
    for event in writes:
        name = str(event.get("name") or "")
        if name not in require_tools:
            continue
        if name in allow_after_approval:
            continue
        if run_meta.get("approval_consumed"):
            continue
        if _has_consumed_approval(execution_id, name):
            continue
        return "FAIL", f"Write tool {name} ran without consumed approval"

    return "PASS", "Writes aligned with guardrail decisions"

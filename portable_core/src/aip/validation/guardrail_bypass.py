"""Detect effective guardrail bypass (no app_context; injectable approval check)."""

from __future__ import annotations

from typing import Any, Callable

from aip.validation.claims import GITHUB_WRITE_TOOLS, GMAIL_SEND_TOOLS

WRITE_TOOLS = GITHUB_WRITE_TOOLS | GMAIL_SEND_TOOLS

ApprovalChecker = Callable[[str, str], bool]


def _default_approval_checker(_execution_id: str, _tool: str) -> bool:
    return False


def check_guardrail_bypass(
    evidence: dict[str, Any],
    run_meta: dict[str, Any],
    *,
    approval_checker: ApprovalChecker | None = None,
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
    checker = approval_checker or _default_approval_checker
    execution_id = str(evidence.get("execution_id") or run_meta.get("execution_id") or "")

    for event in writes:
        name = str(event.get("name") or "")
        if name in denied_tools and not checker(execution_id, name):
            return "FAIL", f"Write tool '{name}' executed despite deny decision"
        # Allowed writes with no recorded decision are treated as OK for portable core.
    return "PASS", ""

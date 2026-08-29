"""Policy evaluation for job writes — DB policies + agent guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aip.db.orm import AgentGuardrailRow, PolicyRow

Decision = Literal["allow", "deny", "hil"]


@dataclass
class PolicyEval:
    decision: Decision
    reason: str


# Default HIL for sensitive writes when no DB policy exists
_DEFAULT_HIL: dict[str, bool] = {
    "github.create_issue": False,
    "github.review_pr": True,
    "github.create_or_update_workflow": True,
    "jira.create_ticket": False,
    "jira.transition_ticket": True,
    "gmail.send_email": True,
    "calendar.create_event": False,
    "calendar.update_event": True,
}


def evaluate_job_policy(
    session: Session,
    *,
    workspace_id: str,
    agent_id: str,
    job_type: str,
) -> PolicyEval:
    # Workspace policy row
    pol = session.scalar(
        select(PolicyRow).where(
            PolicyRow.workspace_id == workspace_id,
            PolicyRow.action == job_type,
        )
    )
    if pol is not None:
        if not pol.allowed:
            return PolicyEval("deny", f"workspace policy denies {job_type}")
        if pol.hil_required:
            return PolicyEval("hil", f"workspace policy requires HIL for {job_type}")
        return PolicyEval("allow", f"workspace policy allows {job_type}")

    # Agent guardrail
    gr = session.scalar(
        select(AgentGuardrailRow).where(
            AgentGuardrailRow.agent_id == agent_id,
            AgentGuardrailRow.tool == job_type,
        )
    )
    if gr is not None:
        mode = (gr.mode or "allow").lower()
        if mode == "deny":
            return PolicyEval("deny", f"agent guardrail denies {job_type}")
        if mode in ("hil", "require_approval"):
            return PolicyEval("hil", f"agent guardrail requires HIL for {job_type}")
        return PolicyEval("allow", f"agent guardrail allows {job_type}")

    if _DEFAULT_HIL.get(job_type, False):
        return PolicyEval("hil", f"default policy requires HIL for {job_type}")
    return PolicyEval("allow", f"default allow for {job_type}")


DEFAULT_POLICY_ACTIONS: list[dict[str, Any]] = [
    {"action": "github.create_issue", "label": "GitHub create issue", "allowed": True, "hil_required": False, "auto_merge": False},
    {"action": "github.review_pr", "label": "GitHub review PR", "allowed": True, "hil_required": True, "auto_merge": False},
    {"action": "github.create_or_update_workflow", "label": "GitHub CI workflow", "allowed": True, "hil_required": True, "auto_merge": False},
    {"action": "jira.create_ticket", "label": "Jira create ticket", "allowed": True, "hil_required": False, "auto_merge": False},
    {"action": "jira.transition_ticket", "label": "Jira transition", "allowed": True, "hil_required": True, "auto_merge": False},
    {"action": "gmail.send_email", "label": "Gmail send", "allowed": True, "hil_required": True, "auto_merge": False},
    {"action": "calendar.create_event", "label": "Calendar create", "allowed": True, "hil_required": False, "auto_merge": False},
    {"action": "calendar.update_event", "label": "Calendar update", "allowed": True, "hil_required": True, "auto_merge": False},
]


def seed_workspace_policies(session: Session, workspace_id: str) -> None:
    """Insert default policies if missing — not operational fake data, config defaults."""
    from datetime import datetime, timezone

    existing = {
        p.action
        for p in session.scalars(select(PolicyRow).where(PolicyRow.workspace_id == workspace_id)).all()
    }
    now = datetime.now(timezone.utc)
    for row in DEFAULT_POLICY_ACTIONS:
        if row["action"] in existing:
            continue
        session.add(
            PolicyRow(
                workspace_id=workspace_id,
                action=row["action"],
                label=row["label"],
                allowed=row["allowed"],
                hil_required=row["hil_required"],
                auto_merge=row["auto_merge"],
                updated_at=now,
            )
        )

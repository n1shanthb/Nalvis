"""Routing Auditor — deterministic groundedness for Director decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aip.director.router import ProposedJob, RoutingDecision
from aip.evidence.contracts import JOB_TYPE_SYSTEM, has_evidence_contract

# Agents synthesized before comment_issue was added may only list create_issue.
_GITHUB_ISSUE_MANAGER_ALIASES: dict[str, str] = {
    "github.comment_issue": "github.create_issue",
}


def _agent_allows_job_type(agent: dict[str, Any], job_type: str) -> bool:
    tools = set(agent.get("toolScope") or agent.get("tool_scope") or [])
    if not tools:
        return True
    if job_type in tools:
        return True
    alias = _GITHUB_ISSUE_MANAGER_ALIASES.get(job_type)
    return bool(alias and alias in tools)


@dataclass
class RoutingAuditResult:
    accepted: list[ProposedJob]
    rejected: list[tuple[ProposedJob, str]]


def extra_github_repos_outside_kg() -> set[str]:
    """Demo/smoke App write targets allowed outside workspace KG repo scope (lowercased)."""
    from aip.config import settings

    out: set[str] = set()
    smoke_o = (settings.smoke_github_owner or "").strip()
    smoke_r = (settings.smoke_github_repo or "").strip()
    if smoke_o and smoke_r:
        out.add(f"{smoke_o}/{smoke_r}".lower())
    app_repo = (settings.smoke_github_app_repo or "").strip()
    if app_repo:
        out.add(app_repo.lower())
    return out


def audit_routing(
    decision: RoutingDecision,
    *,
    agents: list[dict[str, Any]],
    workspace: dict[str, Any],
) -> RoutingAuditResult:
    by_id = {a["id"]: a for a in agents}
    accepted: list[ProposedJob] = []
    rejected: list[tuple[ProposedJob, str]] = []
    scope = workspace.get("scope") or {}

    for job in decision.jobs:
        agent = by_id.get(job.agent_id)
        if not agent:
            rejected.append((job, "unknown agent_id"))
            continue
        if agent.get("status") == "unsupported":
            rejected.append((job, "agent is unsupported"))
            continue
        if agent.get("activation") == "blocked_missing_connector":
            rejected.append((job, "agent blocked_missing_connector"))
            continue
        if not has_evidence_contract(job.job_type):
            rejected.append((job, f"no evidence contract for {job.job_type}"))
            continue
        tools = set(agent.get("toolScope") or agent.get("tool_scope") or [])
        if tools and not _agent_allows_job_type(agent, job.job_type):
            rejected.append((job, f"job_type {job.job_type} not in agent tool allowlist"))
            continue
        system = JOB_TYPE_SYSTEM.get(job.job_type)
        if system == "github":
            repo = job.requested_action.get("repo_full") or (
                f"{job.requested_action.get('owner')}/{job.requested_action.get('repo')}"
                if job.requested_action.get("owner") and job.requested_action.get("repo")
                else ""
            )
            repos = set(scope.get("repos") or [])
            # Align with execute smoke/app write allowlist (webhook repos may not be in KG workspace scope).
            if repos and repo and repo not in repos:
                if str(repo).lower() not in extra_github_repos_outside_kg():
                    rejected.append((job, f"repo {repo} outside workspace scope"))
                    continue
        if system == "jira":
            key = str(
                job.requested_action.get("project_key") or job.requested_action.get("projectKey") or ""
            )
            keys = set(scope.get("jiraKeys") or [])
            if keys and key and key not in keys:
                rejected.append((job, f"jira project {key} outside scope"))
                continue
        if system == "calendar":
            cal = str(job.requested_action.get("calendar_id") or "primary")
            cals = set(scope.get("calendars") or [])
            if cals and cal not in cals and cal != "primary":
                rejected.append((job, f"calendar {cal} outside scope"))
                continue
        accepted.append(job)

    return RoutingAuditResult(accepted=accepted, rejected=rejected)

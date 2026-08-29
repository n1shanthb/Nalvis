"""Routing Auditor — deterministic groundedness for Director decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aip.director.router import ProposedJob, RoutingDecision
from aip.evidence.contracts import JOB_TYPE_SYSTEM, has_evidence_contract


@dataclass
class RoutingAuditResult:
    accepted: list[ProposedJob]
    rejected: list[tuple[ProposedJob, str]]


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
        if tools and job.job_type not in tools:
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
            if repos and repo and repo not in repos:
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

"""Evidence contracts per Authority job_type (required fields for Succeeded)."""

from __future__ import annotations

from typing import Any

# Authority.md — Evidence contracts (authoritative minimum)
EVIDENCE_CONTRACTS: dict[str, frozenset[str]] = {
    "github.create_issue": frozenset({"issue_url", "repo", "issue_number"}),
    "github.review_pr": frozenset({"pr_url"}),  # + review_comment_urls[] or review_id
    "github.create_or_update_workflow": frozenset({"repo", "commit_sha", "file_path", "workflow_url"}),
    "jira.create_ticket": frozenset({"issue_key", "browse_url"}),
    "jira.transition_ticket": frozenset({"issue_key", "transition_id"}),
    "gmail.send_email": frozenset({"message_id", "thread_id"}),
    "calendar.create_event": frozenset({"calendar_id", "event_id"}),
    "calendar.update_event": frozenset({"calendar_id", "event_id"}),
}

# Which connector family a job_type belongs to
JOB_TYPE_SYSTEM: dict[str, str] = {
    "github.create_issue": "github",
    "github.review_pr": "github",
    "github.create_or_update_workflow": "github",
    "jira.create_ticket": "jira",
    "jira.transition_ticket": "jira",
    "gmail.send_email": "gmail",
    "calendar.create_event": "calendar",
    "calendar.update_event": "calendar",
}

EXECUTABLE_SYSTEMS = frozenset({"github", "jira", "gmail", "calendar"})

# Systems that may appear in KG but have no v1 connector
UNSUPPORTED_SYSTEM_ALIASES: dict[str, str] = {
    "slack": "slack",
    "notion": "notion",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "linear": "linear",
    "hubspot": "hubspot",
    "salesforce": "salesforce",
    "discord": "discord",
    "pagerduty": "pagerduty",
    "datadog": "datadog",
}


def has_evidence_contract(job_type: str) -> bool:
    return job_type in EVIDENCE_CONTRACTS


def required_fields(job_type: str) -> frozenset[str]:
    return EVIDENCE_CONTRACTS.get(job_type, frozenset())


def missing_evidence_fields(job_type: str, refs: dict[str, Any] | None) -> list[str]:
    refs = refs or {}
    missing: list[str] = []
    for field in sorted(required_fields(job_type)):
        val = refs.get(field)
        if val is None or val == "" or val == []:
            missing.append(field)
    # github.review_pr: review_comment_urls[] OR review_id
    if job_type == "github.review_pr":
        has_alt = bool(refs.get("review_id")) or bool(refs.get("review_comment_urls"))
        if not has_alt:
            missing.append("review_id|review_comment_urls")
    return missing


def evidence_complete(job_type: str, refs: dict[str, Any] | None) -> bool:
    return len(missing_evidence_fields(job_type, refs)) == 0

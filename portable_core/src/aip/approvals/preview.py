"""Human-readable HIL approval previews — job-type aware, not scenario-specific."""

from __future__ import annotations

import json
from typing import Any

_DEFAULT_GMAIL_REPLY = (
    "Thank you for your message. We have received it and will follow up shortly."
)

_JOB_LABELS: dict[str, str] = {
    "gmail.send_email": "Gmail · Send or reply",
    "github.create_issue": "GitHub · Create issue",
    "github.comment_issue": "GitHub · Comment on issue",
    "github.review_pr": "GitHub · Pull request review",
    "github.create_or_update_workflow": "GitHub · CI workflow change",
    "jira.create_ticket": "Jira · Create ticket",
    "jira.transition_ticket": "Jira · Transition ticket",
    "calendar.create_event": "Calendar · Create event",
    "calendar.update_event": "Calendar · Update event",
}


def _system_key(job_type: str) -> str:
    return (job_type.split(".", 1)[0] if "." in job_type else job_type).lower()


def _field(label: str, value: Any, *, mono: bool = False, link: str | None = None) -> dict[str, Any]:
    text = "" if value is None else str(value).strip()
    row: dict[str, Any] = {"label": label, "value": text or "—"}
    if mono:
        row["mono"] = True
    if link:
        row["link"] = link
    return row


def _github_repo_link(owner: str, repo: str) -> str | None:
    if owner and repo:
        return f"https://github.com/{owner}/{repo}"
    return None


def _resolve_github_repo(action: dict[str, Any]) -> tuple[str, str]:
    if action.get("repo_full") and "/" in str(action["repo_full"]):
        o, r = str(action["repo_full"]).split("/", 1)
        return o.strip(), r.strip()
    owner = str(action.get("owner") or "").strip()
    repo = str(action.get("repo") or "").strip()
    if repo and "/" in repo and not owner:
        o, r = repo.split("/", 1)
        return o.strip(), r.strip()
    return owner, repo


def build_approval_preview(
    *,
    job_type: str,
    requested_action: dict[str, Any] | None,
    job_title: str = "",
    policy_reason: str = "",
    run_signal: dict[str, Any] | None = None,
    agent_name: str = "",
) -> dict[str, Any]:
    """Structured preview for Approvals UI + diff_preview storage."""
    action = dict(requested_action or {})
    signal = dict(run_signal or {})
    system = _system_key(job_type)
    action_label = _JOB_LABELS.get(job_type, job_type.replace(".", " · ").replace("_", " "))

    fields: list[dict[str, Any]] = []
    impact: list[str] = []
    links: list[dict[str, str]] = []
    editable_key = "body"
    editable_default = ""
    trigger: dict[str, Any] | None = None

    channel = str(signal.get("channel") or "").lower()
    if channel:
        trigger = {
            "channel": channel,
            "title": _trigger_title(signal),
            "rows": _trigger_rows(signal),
        }

    if job_type == "gmail.send_email":
        message_id = str(action.get("message_id") or "").strip()
        reply_to = str(action.get("reply_to") or action.get("to") or "").strip()
        subject = str(action.get("subject") or "").strip()
        body = str(action.get("body") or "").strip()
        editable_default = body or _DEFAULT_GMAIL_REPLY
        fields.extend(
            [
                _field("Action", "Reply in thread" if message_id else "Send new email"),
                _field("To", reply_to or str(action.get("to") or "")),
                _field("Subject", subject or "(same thread subject)"),
            ]
        )
        if message_id:
            fields.append(_field("Thread / message ID", message_id, mono=True))
        if signal.get("from"):
            fields.append(_field("Inbound from", str(signal.get("from"))))
        if signal.get("subject") and not subject:
            fields.append(_field("Inbound subject", str(signal.get("subject"))))
        if signal.get("snippet") or signal.get("body_summary"):
            fields.append(
                _field(
                    "Inbound preview",
                    str(signal.get("snippet") or signal.get("body_summary") or "")[:500],
                )
            )
        impact.append("Sends email from the connected Gmail account to an external recipient.")
        if reply_to:
            impact.append(f"Recipient: {reply_to}")

    elif job_type == "github.create_issue":
        owner, repo = _resolve_github_repo(action)
        title = str(action.get("title") or job_title or "").strip()
        body = str(action.get("body") or "").strip()
        editable_key = "body"
        editable_default = body
        repo_link = _github_repo_link(owner, repo)
        fields.extend(
            [
                _field("Repository", f"{owner}/{repo}" if owner and repo else "—", link=repo_link),
                _field("Issue title", title),
            ]
        )
        if body:
            fields.append(_field("Issue body", body))
        impact.append(f"Creates a new GitHub issue in {owner}/{repo}." if owner and repo else "Creates a new GitHub issue.")

    elif job_type == "github.comment_issue":
        owner, repo = _resolve_github_repo(action)
        issue_number = action.get("issue_number") or action.get("number")
        body = str(action.get("body") or action.get("comment") or "").strip()
        editable_key = "body"
        editable_default = body or f"[agentsuite] Comment on issue #{issue_number}"
        issue_url = str(action.get("issue_url") or action.get("html_url") or "").strip()
        if not issue_url and owner and repo and issue_number is not None:
            issue_url = f"https://github.com/{owner}/{repo}/issues/{issue_number}"
        fields.extend(
            [
                _field("Repository", f"{owner}/{repo}" if owner and repo else "—", link=_github_repo_link(owner, repo)),
                _field("Issue #", str(issue_number) if issue_number is not None else "—"),
                _field("Comment", body or editable_default),
            ]
        )
        if issue_url:
            links.append({"label": "Open issue", "href": issue_url})
        impact.append("Posts a public comment on the GitHub issue.")

    elif job_type == "github.review_pr":
        owner, repo = _resolve_github_repo(action)
        pull_number = action.get("pull_number") or action.get("pr_number") or action.get("number")
        body = str(action.get("body") or action.get("comment") or "").strip()
        event = str(action.get("event") or "COMMENT").upper()
        editable_key = "body"
        editable_default = body or "Review body will be drafted before approval."
        pr_url = f"https://github.com/{owner}/{repo}/pull/{pull_number}" if owner and repo and pull_number else ""
        fields.extend(
            [
                _field("Repository", f"{owner}/{repo}" if owner and repo else "—", link=_github_repo_link(owner, repo)),
                _field("Pull request", f"#{pull_number}" if pull_number is not None else "—", link=pr_url or None),
                _field("Review type", event),
                _field("Review comment", body or editable_default),
            ]
        )
        if pr_url:
            links.append({"label": "Open pull request", "href": pr_url})
        impact.append(f"Submits a {event} review on the pull request.")

    elif job_type == "github.create_or_update_workflow":
        owner, repo = _resolve_github_repo(action)
        file_path = str(action.get("file_path") or action.get("path") or ".github/workflows/agentsuite-smoke.yml")
        message = str(action.get("message") or f"Update {file_path}")
        content = str(action.get("content") or action.get("workflow_yaml") or "")
        editable_key = "content"
        editable_default = content
        blob_url = f"https://github.com/{owner}/{repo}/blob/HEAD/{file_path}" if owner and repo else ""
        fields.extend(
            [
                _field("Repository", f"{owner}/{repo}" if owner and repo else "—", link=_github_repo_link(owner, repo)),
                _field("Workflow file", file_path, link=blob_url or None),
                _field("Commit message", message),
            ]
        )
        if content:
            fields.append(_field("Workflow content", content[:800] + ("…" if len(content) > 800 else ""), mono=True))
        impact.append("Creates or updates a GitHub Actions workflow file on the default branch.")

    elif job_type == "jira.create_ticket":
        project_key = str(action.get("project_key") or action.get("projectKey") or "").strip()
        summary = str(action.get("summary") or action.get("title") or job_title or "").strip()
        description = str(action.get("description") or action.get("body") or "").strip()
        editable_key = "description"
        editable_default = description
        fields.extend(
            [
                _field("Project", project_key or "—"),
                _field("Summary", summary),
            ]
        )
        if description:
            fields.append(_field("Description", description))
        impact.append(f"Creates a Jira ticket in project {project_key}." if project_key else "Creates a Jira ticket.")

    elif job_type == "jira.transition_ticket":
        issue_key = str(action.get("issue_key") or action.get("issueKey") or "").strip()
        transition = str(
            action.get("transition_name")
            or action.get("transitionName")
            or action.get("transition_id")
            or action.get("transitionId")
            or ""
        ).strip()
        fields.extend(
            [
                _field("Issue key", issue_key, mono=True),
                _field("Transition", transition or "—"),
            ]
        )
        impact.append(f"Changes workflow state for Jira issue {issue_key}.")

    elif job_type == "calendar.create_event":
        summary = str(action.get("summary") or action.get("title") or job_title or "").strip()
        start = str(action.get("start") or "").strip()
        end = str(action.get("end") or "").strip()
        calendar_id = str(action.get("calendar_id") or "primary")
        description = str(action.get("description") or "").strip()
        editable_key = "description"
        editable_default = description
        fields.extend(
            [
                _field("Calendar", calendar_id),
                _field("Event title", summary),
                _field("Start", start or "—"),
                _field("End", end or "—"),
            ]
        )
        if description:
            fields.append(_field("Description", description))
        impact.append("Creates a calendar event on the connected Google account.")

    elif job_type == "calendar.update_event":
        calendar_id = str(action.get("calendar_id") or "primary")
        event_id = str(action.get("event_id") or "").strip()
        summary = str(action.get("summary") or "").strip()
        editable_key = "description"
        editable_default = str(action.get("description") or "")
        fields.extend(
            [
                _field("Calendar", calendar_id),
                _field("Event ID", event_id, mono=True),
                _field("New title", summary or "(unchanged)"),
                _field("Start", str(action.get("start") or "—")),
                _field("End", str(action.get("end") or "—")),
            ]
        )
        impact.append("Updates an existing calendar event.")

    else:
        for key, val in action.items():
            if val is not None and str(val).strip():
                fields.append(_field(key.replace("_", " ").title(), str(val)[:500]))
        editable_default = json.dumps(action, indent=2)
        editable_key = ""

    summary = job_title.strip() or policy_reason.strip() or action_label
    if policy_reason and policy_reason not in summary:
        summary = f"{summary} — {policy_reason}"

    context: dict[str, Any] = {
        "system": system,
        "actionLabel": action_label,
        "summary": summary,
        "agentName": agent_name,
        "fields": fields,
        "impact": impact,
        "links": links,
        "editableKey": editable_key,
        "editableLabel": _editable_label(editable_key),
        "editableDefault": editable_default,
        "requestedAction": action,
    }
    if trigger:
        context["trigger"] = trigger

    return {
        "before": "",
        "after": json.dumps(action, indent=2, default=str),
        "context": context,
    }


def _editable_label(key: str) -> str:
    return {
        "body": "Message body",
        "content": "Workflow YAML",
        "description": "Description",
        "comment": "Comment",
    }.get(key, "Editable payload")


def _trigger_title(signal: dict[str, Any]) -> str:
    channel = str(signal.get("channel") or "signal").title()
    subject = str(signal.get("subject") or signal.get("title") or "").strip()
    if subject:
        return f"{channel} · {subject}"
    event = str(signal.get("event") or signal.get("action") or "").strip()
    if event:
        return f"{channel} · {event}"
    return f"Inbound {channel}"


def _trigger_rows(signal: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    mapping = [
        ("From", signal.get("from") or signal.get("sender")),
        ("To", signal.get("to")),
        ("Subject", signal.get("subject")),
        ("Repository", signal.get("repo") or signal.get("repo_full")),
        ("Issue / PR", signal.get("issue_number") or signal.get("pull_number")),
        ("Preview", (signal.get("snippet") or signal.get("body_summary") or "")[:400]),
    ]
    for label, val in mapping:
        text = "" if val is None else str(val).strip()
        if text:
            rows.append({"label": label, "value": text})
    return rows

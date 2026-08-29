"""Jira webhook event extraction + Spec prompt building (no FastAPI)."""

from __future__ import annotations

import re
from typing import Any

from aip.config import settings
from aip.webhooks.jira_inventory import jira_webhook_id


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_from_adf_or_str(value: Any) -> str:
    """Jira Cloud may send description/comment as ADF or plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        # Flatten Atlassian Document Format lightly
        texts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if isinstance(node.get("text"), str):
                    texts.append(node["text"])
                for child in node.get("content") or []:
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(value)
        return " ".join(texts).strip()
    return str(value).strip()


def extract_cloud_id(payload: dict[str, Any], issue: dict[str, Any]) -> str:
    configured = (settings.atlassian_cloud_id or "").strip()
    if configured:
        return configured
    for key in ("cloudId", "cloudid", "cloud_id"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    self_url = str(issue.get("self") or "")
    # https://api.atlassian.com/ex/jira/{cloudId}/rest/...
    match = re.search(r"/ex/jira/([0-9a-fA-F-]{20,})/", self_url)
    if match:
        return match.group(1)
    return ""


def extract_context(payload: dict[str, Any]) -> dict[str, Any]:
    webhook_event = str(
        payload.get("webhookEvent") or payload.get("event") or "unknown"
    ).strip()
    wid = jira_webhook_id(webhook_event)
    issue = _as_dict(payload.get("issue"))
    fields = _as_dict(issue.get("fields"))
    project = _as_dict(fields.get("project"))
    comment = _as_dict(payload.get("comment"))
    user = _as_dict(payload.get("user"))
    author = _as_dict(comment.get("author")) if comment else {}
    actor = author or user

    issue_key = str(issue.get("key") or "").strip()
    project_key = str(project.get("key") or "").strip()
    if not project_key and "-" in issue_key:
        project_key = issue_key.split("-", 1)[0]

    summary = str(fields.get("summary") or "").strip()
    description = _text_from_adf_or_str(fields.get("description"))
    body = _text_from_adf_or_str(comment.get("body")) if comment else description
    issue_type = str(_as_dict(fields.get("issuetype")).get("name") or "").strip()
    status = str(_as_dict(fields.get("status")).get("name") or "").strip()

    account_id = str(actor.get("accountId") or actor.get("account_id") or "").strip()
    sender = str(
        actor.get("displayName")
        or actor.get("emailAddress")
        or actor.get("name")
        or account_id
        or ""
    ).strip()
    sender_email = str(actor.get("emailAddress") or "").strip()

    html_url = ""
    self_url = str(issue.get("self") or "")
    # Prefer browse URL when site hostname is present
    site_match = re.match(r"(https://[^/]+\.atlassian\.net)/", self_url)
    if site_match and issue_key:
        html_url = f"{site_match.group(1)}/browse/{issue_key}"
    elif issue_key:
        html_url = issue_key

    cloud_id = extract_cloud_id(payload, issue)

    return {
        "event": webhook_event,
        "webhook_id": wid,
        "cloud_id": cloud_id,
        "project_key": project_key,
        "issue_key": issue_key,
        "issue_id": str(issue.get("id") or "").strip(),
        "title": summary,
        "description": description,
        "body": body,
        "issue_type": issue_type,
        "status": status,
        "html_url": html_url,
        "sender": sender,
        "sender_account_id": account_id,
        "sender_email": sender_email,
        "comment_id": str(comment.get("id") or "").strip() if comment else "",
        "is_comment": bool(comment) or wid.startswith("comment_"),
    }


def should_skip_jira_actor(context: dict[str, Any]) -> tuple[bool, str]:
    """Skip when the webhook actor is our bot or any Atlassian service account."""
    bot_id = (settings.jira_bot_account_id or "").strip()
    bot_email = (settings.jira_bot_email or "").strip().lower()
    account_id = str(context.get("sender_account_id") or "").strip()
    email = str(context.get("sender_email") or "").strip().lower()
    if bot_id and account_id and account_id == bot_id:
        return True, "bot_account"
    if bot_email and email and email == bot_email:
        return True, "bot_email"
    # Any service-account actor is our (or another) automation — never reply-loop.
    if email.endswith("@serviceaccount.atlassian.com"):
        return True, "service_account"
    return False, ""


def spec_kind_for_binding(spec_id: str) -> str:
    sid = (spec_id or "").lower()
    if "comment" in sid or "mention" in sid:
        return "jira_comment"
    if "issue" in sid or "triage" in sid:
        return "jira_issue"
    return "jira_issue"


def build_spec_prompt(kind: str, context: dict[str, Any]) -> str:
    cloud = (context.get("cloud_id") or "").strip()
    cloud_line = (
        f"cloudId: {cloud} (USE THIS — do not call getAccessibleAtlassianResources)"
        if cloud
        else (
            "cloudId: unknown — call getAccessibleAtlassianResources ONCE, "
            "then use the cloudId for the akassh / target site"
        )
    )
    key = context.get("issue_key") or "?"
    title = context.get("title") or ""
    description = context.get("description") or ""
    body = context.get("body") or ""
    project = context.get("project_key") or ""
    url = context.get("html_url") or ""
    sender = context.get("sender") or ""

    if kind == "jira_comment":
        return (
            f"Jira comment event on {key}.\n"
            f"{cloud_line}\n"
            f"project: {project}\n"
            f"issue: {key} — {title}\n"
            f"URL: {url}\n"
            f"Sender: {sender}\n\n"
            f"Comment body:\n{body}\n\n"
            "1) Use cloudId from context when present.\n"
            "2) Read the issue with getJiraIssue.\n"
            "3) Post ONE helpful reply with addCommentToJiraIssue.\n"
            "Never reply to your own comments. Stay within this issue."
        )

    return (
        f"New/updated Jira issue {key}.\n"
        f"{cloud_line}\n"
        f"project: {project}\n"
        f"type: {context.get('issue_type') or '?'}\n"
        f"status: {context.get('status') or '?'}\n"
        f"title: {title}\n"
        f"URL: {url}\n"
        f"Sender: {sender}\n\n"
        f"Description:\n{description or body}\n\n"
        "1) Use cloudId from context when present — do not loop on "
        "getAccessibleAtlassianResources if it returns 401.\n"
        "2) Read the issue with getJiraIssue.\n"
        "3) Post ONE triage comment via addCommentToJiraIssue.\n"
        "Do not invent private data. Never exit silently."
    )

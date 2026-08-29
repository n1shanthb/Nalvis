"""Connector smoke / health helpers for GitHub, Jira, Gmail, Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from aip.config import settings


def health_snapshot() -> dict[str, Any]:
    from aip.integrations.github_app import github_app_configured, resolve_github_token
    from aip.integrations.gmail_oauth import gmail_configured, gmail_oauth_error
    from aip.tools.calendar import calendar_configured

    gh_token = None
    gh_err = None
    try:
        gh_token = bool(resolve_github_token())
    except Exception as exc:  # noqa: BLE001
        gh_err = str(exc)[:200]

    jira_token = bool((settings.atlassian_mcp_token or settings.jira_mcp_token or "").strip())
    gmail_err = None
    try:
        gmail_err = gmail_oauth_error() if gmail_configured() else "not_configured"
    except Exception as exc:  # noqa: BLE001
        gmail_err = str(exc)[:200]

    return {
        "github": {
            "app_configured": github_app_configured(),
            "token_resolvable": gh_token,
            "mcp_enabled": settings.connected_system_github_mcp_enabled,
            "mcp_url": settings.connected_system_github_mcp_url,
            "error": gh_err,
        },
        "jira": {
            "token_configured": jira_token,
            "mcp_enabled": settings.connected_system_jira_mcp_enabled,
            "mcp_url": settings.connected_system_jira_mcp_url,
        },
        "gmail": {
            "configured": gmail_configured(),
            "enabled": settings.connected_system_gmail_enabled,
            "oauth_error": gmail_err,
        },
        "calendar": {
            "configured": calendar_configured(),
            "enabled": settings.connected_system_calendar_enabled,
        },
    }


def smoke_github(*, title: str | None = None) -> dict[str, Any]:
    """Prefer GitHub MCP issue_write; REST create_issue is fallback."""
    from aip.connectors.github_smoke import smoke_github_mcp_issue

    return smoke_github_mcp_issue(title=title)


def smoke_github_mcp_list() -> dict[str, Any]:
    from aip.connectors.mcp_client import github_mcp_headers, list_mcp_tools

    url = settings.connected_system_github_mcp_url
    try:
        headers = github_mcp_headers()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return list_mcp_tools(url=url, headers=headers, name="github_mcp")


def smoke_jira_mcp_create(*, summary: str | None = None) -> dict[str, Any]:
    from aip.connectors.mcp_client import call_mcp_tool, jira_mcp_headers

    try:
        headers = jira_mcp_headers()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    cloud_id = (settings.atlassian_cloud_id or "").strip()
    if not cloud_id:
        resources = call_mcp_tool(
            url=settings.connected_system_jira_mcp_url,
            headers=headers,
            name="jira_mcp",
            tool_name="getAccessibleAtlassianResources",
            arguments={},
        )
        if not resources.get("ok"):
            return {"ok": False, "error": "cloudId missing and discovery failed", "discover": resources}
        cloud_id = _first_cloud_id(resources.get("result"))
    if not cloud_id:
        return {"ok": False, "error": "Set ATLASSIAN_CLOUD_ID"}

    project = (settings.smoke_jira_project_key or "").strip()
    if not project:
        listed = call_mcp_tool(
            url=settings.connected_system_jira_mcp_url,
            headers=headers,
            name="jira_mcp",
            tool_name="getVisibleJiraProjects",
            arguments={"cloudId": cloud_id},
        )
        if not listed.get("ok"):
            return {"ok": False, "error": "Set SMOKE_JIRA_PROJECT_KEY", "discover": listed}
        project = _first_jira_project_key(listed.get("result"))
    if not project:
        return {"ok": False, "error": "No visible Jira project found; set SMOKE_JIRA_PROJECT_KEY"}

    tool_name = "createJiraIssue"
    args: dict[str, Any] = {
        "cloudId": cloud_id,
        "projectKey": project,
        "summary": summary or f"[agentsuite smoke] {datetime.now(timezone.utc).isoformat()}",
        "description": "Created by agentsuite connector smoke test.",
        "issueTypeName": "Task",
    }
    result = call_mcp_tool(
        url=settings.connected_system_jira_mcp_url,
        headers=headers,
        name="jira_mcp",
        tool_name=tool_name,
        arguments=args,
    )
    if not result.get("ok"):
        return {"ok": False, "system": "jira", "error": "createJiraIssue failed", "last": result}
    evidence = _jira_evidence_from_result(result.get("result"), project)
    if not evidence.get("issue_key"):
        return {
            "ok": False,
            "system": "jira",
            "error": "create returned no issue key",
            "result": result.get("result"),
        }
    return {
        "ok": True,
        "system": "jira",
        "tool": tool_name,
        "evidence": evidence,
        "result": str(result.get("result"))[:500],
    }


def _first_cloud_id(payload: Any) -> str:
    import json
    import re

    text = payload
    if isinstance(payload, dict) and "content" in payload:
        parts = payload.get("content") or []
        text = "\n".join(str(x) for x in parts) if isinstance(parts, list) else parts
    blob = str(text or "")
    try:
        data = json.loads(blob) if blob.strip().startswith(("{", "[")) else None
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return str(data[0].get("id") or data[0].get("cloudId") or "").strip()
    if isinstance(data, dict):
        return str(data.get("id") or data.get("cloudId") or "").strip()
    m = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        blob,
        re.I,
    )
    return m.group(0) if m else ""


def _first_jira_project_key(payload: Any) -> str:
    text = payload
    if isinstance(payload, dict) and "content" in payload:
        text = payload.get("content")
    if isinstance(text, list):
        text = "\n".join(str(x) for x in text)
    blob = str(text or "")
    # Prefer JSON-looking "key": "ABC"
    import json
    import re

    try:
        data = json.loads(blob) if blob.strip().startswith(("{", "[")) else None
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and row.get("key"):
                return str(row["key"]).strip()
    if isinstance(data, dict):
        for row in data.get("values") or data.get("projects") or []:
            if isinstance(row, dict) and row.get("key"):
                return str(row["key"]).strip()
    m = re.search(r'"key"\s*:\s*"([A-Z][A-Z0-9]+)"', blob)
    return m.group(1) if m else ""


def _jira_evidence_from_result(payload: Any, project: str) -> dict[str, Any]:
    import json
    import re

    blob = payload
    if isinstance(payload, dict) and "content" in payload:
        parts = payload.get("content") or []
        blob = "\n".join(str(p) for p in parts) if isinstance(parts, list) else parts
    text = str(blob or "")
    key = ""
    try:
        data = json.loads(text) if text.strip().startswith(("{", "[")) else None
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        key = str(data.get("key") or data.get("issueKey") or "")
    if not key:
        m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text)
        key = m.group(1) if m else ""
    return {
        "issue_key": key,
        "project_key": project,
        "browse_url": f"https://jira.atlassian.com/browse/{key}" if key else "",
    }


def smoke_gmail_send(*, to: str | None = None) -> dict[str, Any]:
    from aip.tools.gmail import send_email

    recipient = (to or settings.gmail_user or "").strip()
    if not recipient:
        return {"ok": False, "error": "Set GMAIL_USER (or pass to=)"}
    result = send_email(
        {
            "to": recipient,
            "subject": f"[agentsuite smoke] {datetime.now(timezone.utc).isoformat()}",
            "body": "Created by agentsuite Gmail native smoke test.",
        }
    )
    if result.get("error"):
        return {"ok": False, "system": "gmail", "error": result}
    return {
        "ok": True,
        "system": "gmail",
        "evidence": {
            "message_id": result.get("message_id"),
            "thread_id": result.get("thread_id"),
        },
        "raw": result,
    }


def smoke_calendar_create() -> dict[str, Any]:
    from aip.tools.calendar import create_event

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(minutes=30)
    result = create_event(
        {
            "calendar_id": "primary",
            "summary": f"[agentsuite smoke] {start.isoformat()}",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "description": "Created by agentsuite Calendar native smoke test.",
        }
    )
    if result.get("error"):
        return {"ok": False, "system": "calendar", "error": result}
    event = result.get("event") if isinstance(result.get("event"), dict) else result
    return {
        "ok": True,
        "system": "calendar",
        "evidence": {
            "event_id": event.get("id") if isinstance(event, dict) else None,
            "calendar_id": "primary",
            "html_link": event.get("htmlLink") if isinstance(event, dict) else None,
        },
        "raw": result,
    }

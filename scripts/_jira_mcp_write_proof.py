"""Discover Atlassian cloudId and create a Jira issue via MCP."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

from aip.config import settings
from aip.connectors.mcp_client import call_mcp_tool, jira_mcp_headers


def _blob(payload: Any) -> str:
    if isinstance(payload, dict) and "content" in payload:
        parts = payload.get("content") or []
        return "\n".join(str(p) for p in parts) if isinstance(parts, list) else str(parts)
    return str(payload or "")


def _parse_jsonish(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Sometimes MCP wraps JSON in prose; extract first object/array.
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None


def discover_cloud_id(headers: dict[str, str]) -> str:
    configured = (settings.atlassian_cloud_id or "").strip()
    if configured:
        return configured
    listed = call_mcp_tool(
        url=settings.connected_system_jira_mcp_url,
        headers=headers,
        name="jira_mcp",
        tool_name="getAccessibleAtlassianResources",
        arguments={},
    )
    if not listed.get("ok"):
        raise RuntimeError(f"getAccessibleAtlassianResources failed: {listed}")
    data = _parse_jsonish(_blob(listed.get("result")))
    if isinstance(data, list) and data:
        row = data[0]
        if isinstance(row, dict):
            return str(row.get("id") or row.get("cloudId") or "").strip()
    if isinstance(data, dict):
        return str(data.get("id") or data.get("cloudId") or "").strip()
    # UUID-ish fallback from text
    m = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        _blob(listed.get("result")),
        re.I,
    )
    return m.group(0) if m else ""


def discover_project_key(headers: dict[str, str], cloud_id: str) -> str:
    configured = (settings.smoke_jira_project_key or "").strip()
    if configured:
        return configured
    listed = call_mcp_tool(
        url=settings.connected_system_jira_mcp_url,
        headers=headers,
        name="jira_mcp",
        tool_name="getVisibleJiraProjects",
        arguments={"cloudId": cloud_id},
    )
    if not listed.get("ok"):
        raise RuntimeError(f"getVisibleJiraProjects failed: {listed}")
    data = _parse_jsonish(_blob(listed.get("result")))
    rows = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("values") or data.get("projects") or []
    for row in rows:
        if isinstance(row, dict) and row.get("key"):
            return str(row["key"]).strip()
    m = re.search(r'"key"\s*:\s*"([A-Z][A-Z0-9]+)"', _blob(listed.get("result")))
    return m.group(1) if m else ""


def main() -> int:
    headers = jira_mcp_headers()
    cloud_id = discover_cloud_id(headers)
    print("cloud_id_set", bool(cloud_id), cloud_id[:8] + "…" if cloud_id else "")
    if not cloud_id:
        print("FAIL: no cloudId")
        return 1
    project = discover_project_key(headers, cloud_id)
    print("project", project or "<none>")
    if not project:
        print("FAIL: no project key")
        return 1

    summary = f"[agentsuite smoke] {datetime.now(timezone.utc).isoformat()}"
    created = call_mcp_tool(
        url=settings.connected_system_jira_mcp_url,
        headers=headers,
        name="jira_mcp",
        tool_name="createJiraIssue",
        arguments={
            "cloudId": cloud_id,
            "projectKey": project,
            "issueTypeName": "Task",
            "summary": summary,
            "description": "Created by agentsuite Jira MCP smoke test.",
        },
    )
    blob = _blob(created.get("result"))
    print("create_ok", created.get("ok"))
    print("create_result", blob[:800])
    data = _parse_jsonish(blob)
    key = ""
    if isinstance(data, dict):
        key = str(data.get("key") or data.get("issueKey") or "")
    if not key:
        m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", blob)
        key = m.group(1) if m else ""
    ok = bool(created.get("ok") and key and "error" not in blob.lower())
    print("evidence", {"issue_key": key, "project_key": project})
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

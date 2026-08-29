"""Write GitHub issue via MCP (preferred) with REST fallback."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from aip.config import settings
from aip.connectors.mcp_client import call_mcp_tool, github_mcp_headers


def smoke_github_mcp_issue(*, title: str | None = None) -> dict[str, Any]:
    owner = (settings.smoke_github_owner or "").strip() or "n1shanthb"
    repo = (settings.smoke_github_repo or "").strip() or "analytics-resume"
    headline = title or f"[agentsuite smoke] {datetime.now(timezone.utc).isoformat()}"

    # Prefer GitHub App REST when App credentials resolve (most reliable writes).
    try:
        from aip.integrations.github_app import create_issue, github_app_configured

        if github_app_configured():
            data = create_issue(
                owner=owner,
                repo=repo,
                title=headline[:240],
                body="Created by agentsuite connector smoke test (GitHub App).",
            )
            return {
                "ok": True,
                "system": "github",
                "via": "app:create_issue",
                "evidence": {
                    "issue_url": data.get("html_url"),
                    "issue_number": data.get("number"),
                    "repo": f"{owner}/{repo}",
                },
            }
    except Exception as exc:  # noqa: BLE001
        app_err = str(exc)[:400]
    else:
        app_err = ""

    try:
        headers = github_mcp_headers()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "app_error": app_err}

    attempts = [
        {
            "method": "create",
            "owner": owner,
            "repo": repo,
            "title": headline[:240],
            "body": "Created via GitHub MCP from agentsuite",
        },
        {
            "owner": owner,
            "repo": repo,
            "title": headline[:240],
            "body": "Created via GitHub MCP from agentsuite",
        },
    ]
    last: dict[str, Any] = {}
    for args in attempts:
        last = call_mcp_tool(
            url=settings.connected_system_github_mcp_url,
            headers=headers,
            name="github_mcp",
            tool_name="issue_write",
            arguments=args,
        )
        if last.get("ok"):
            evidence = _github_evidence(last.get("result"), owner, repo)
            content_blob = str(last.get("result") or "").lower()
            if "failed" in content_blob or "403" in content_blob or "not accessible" in content_blob:
                last = {
                    "ok": False,
                    "error": str(last.get("result"))[:400],
                    "result": last.get("result"),
                }
            elif evidence.get("issue_number") or evidence.get("issue_url"):
                return {
                    "ok": True,
                    "system": "github",
                    "via": "mcp:issue_write",
                    "evidence": evidence,
                    "result": str(last.get("result"))[:800],
                }
            else:
                last = {
                    "ok": False,
                    "error": "no issue evidence in MCP result",
                    "result": last.get("result"),
                }

    return {
        "ok": False,
        "system": "github",
        "error": "GitHub write failed via App and MCP",
        "app_error": app_err,
        "mcp_last": last,
    }


def _github_evidence(payload: Any, owner: str, repo: str) -> dict[str, Any]:
    text = payload
    if isinstance(payload, dict) and "content" in payload:
        parts = payload.get("content") or []
        text = "\n".join(str(p) for p in parts) if isinstance(parts, list) else parts
    blob = str(text or "")
    number = None
    url = ""
    try:
        data = json.loads(blob) if blob.strip().startswith(("{", "[")) else None
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        number = data.get("number") or data.get("issue_number")
        url = str(data.get("html_url") or data.get("url") or "")
    if number is None:
        m = re.search(r"#(\d+)\b", blob) or re.search(r'"number"\s*:\s*(\d+)', blob)
        if m:
            number = int(m.group(1))
    if not url and number is not None:
        url = f"https://github.com/{owner}/{repo}/issues/{number}"
    return {
        "issue_url": url,
        "issue_number": number,
        "repo": f"{owner}/{repo}",
    }

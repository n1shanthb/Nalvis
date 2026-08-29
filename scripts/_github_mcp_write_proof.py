"""Prove a GitHub write via MCP: create a throwaway repo then an issue."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

from aip.config import settings
from aip.connectors.mcp_client import call_mcp_tool, github_mcp_headers


def main() -> int:
    headers = github_mcp_headers()
    url = settings.connected_system_github_mcp_url
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    name = f"agentsuite-smoke-{stamp}"
    created = call_mcp_tool(
        url=url,
        headers=headers,
        name="github_mcp",
        tool_name="create_repository",
        arguments={
            "name": name,
            "description": "Temporary agentsuite connector smoke repo",
            "private": True,
            "autoInit": True,
        },
    )
    print("create_repository:", json.dumps(created, default=str)[:1200])
    if not created.get("ok"):
        return 1
    blob = str(created.get("result") or "")
    owner = "n1shanthb"
    m = re.search(r"github\.com/([^/\s\"]+)/([^/\s\"]+)", blob)
    if m:
        owner, name = m.group(1), m.group(2).removesuffix(".git")
    # wait briefly for repo readiness
    time.sleep(2)
    issue = call_mcp_tool(
        url=url,
        headers=headers,
        name="github_mcp",
        tool_name="issue_write",
        arguments={
            "method": "create",
            "owner": owner,
            "repo": name,
            "title": f"[agentsuite smoke] {stamp}",
            "body": "Created via GitHub MCP from agentsuite",
        },
    )
    print("issue_write:", json.dumps(issue, default=str)[:1200])
    text = str(issue.get("result") or "").lower()
    ok = bool(issue.get("ok")) and "failed" not in text and "403" not in text
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

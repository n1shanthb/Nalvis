"""Prove GitHub MCP issue_write using App installation token."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

from aip.config import settings
from aip.connectors.mcp_client import call_mcp_tool, github_mcp_headers
from aip.integrations.github_app import github_app_configured, resolve_github_token


def main() -> int:
    print("app_configured", github_app_configured())
    token = resolve_github_token() or ""
    print("token_len", len(token))
    headers = github_mcp_headers()
    owner = (settings.smoke_github_owner or "n1shanthb").strip()
    repo = (settings.smoke_github_repo or "analytics-resume").strip()
    title = f"[agentsuite mcp smoke] {datetime.now(timezone.utc).isoformat()}"
    result = call_mcp_tool(
        url=settings.connected_system_github_mcp_url,
        headers=headers,
        name="github_mcp",
        tool_name="issue_write",
        arguments={
            "method": "create",
            "owner": owner,
            "repo": repo,
            "title": title[:240],
            "body": "Created via GitHub MCP (App installation token) from agentsuite",
        },
    )
    blob = str(result.get("result") or "")
    print("mcp_ok", result.get("ok"))
    print("result", blob[:900])
    low = blob.lower()
    number = None
    m = re.search(r'"number"\s*:\s*(\d+)', blob) or re.search(r"#(\d+)\b", blob)
    if m:
        number = int(m.group(1))
    url_m = re.search(r"https://github\.com/[^\s\"']+/issues/\d+", blob)
    url = url_m.group(0) if url_m else (
        f"https://github.com/{owner}/{repo}/issues/{number}" if number else ""
    )
    ok = bool(result.get("ok") and "failed" not in low and "403" not in low and (number or url))
    print("evidence", {"issue_number": number, "issue_url": url, "repo": f"{owner}/{repo}"})
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

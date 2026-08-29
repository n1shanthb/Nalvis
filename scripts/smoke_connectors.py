#!/usr/bin/env python
"""Smoke-test connectors: GitHub (REST+MCP probe), Jira MCP, Gmail native, Calendar native.

Usage:
  python scripts/smoke_connectors.py --health
  python scripts/smoke_connectors.py --systems github,gmail,calendar
  python scripts/smoke_connectors.py --systems jira
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    parser.add_argument(
        "--systems",
        default="github,jira,gmail,calendar",
        help="Comma-separated: github,jira,gmail,calendar",
    )
    parser.add_argument("--include-jira", action="store_true", default=True, help="Enable Jira smoke")
    parser.add_argument("--skip-jira", action="store_true", help="Skip Jira smoke")
    args = parser.parse_args()

    from aip.connectors import smoke as connector_smoke

    if args.health:
        print(json.dumps(connector_smoke.health_snapshot(), indent=2))
        return 0

    wanted = {s.strip().lower() for s in args.systems.split(",") if s.strip()}
    if args.skip_jira:
        wanted.discard("jira")
    results: dict = {}
    if "github" in wanted:
        results["github"] = connector_smoke.smoke_github()
        results["github_mcp"] = connector_smoke.smoke_github_mcp_list()
    if "jira" in wanted:
        results["jira"] = connector_smoke.smoke_jira_mcp_create()
    if "gmail" in wanted:
        results["gmail"] = connector_smoke.smoke_gmail_send()
    if "calendar" in wanted:
        results["calendar"] = connector_smoke.smoke_calendar_create()

    print(json.dumps(results, indent=2, default=str))
    ok = True
    for key, value in results.items():
        if key == "github_mcp":
            if not (isinstance(value, dict) and (value.get("ok") or value.get("available"))):
                ok = False
            continue
        if not (isinstance(value, dict) and value.get("ok")):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

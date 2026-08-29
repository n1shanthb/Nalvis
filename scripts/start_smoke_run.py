"""Start a CompanyRunWorkflow smoke with structured plan (GitHub+Gmail+Calendar).

Usage (API + worker must be running):
  python scripts/start_smoke_run.py

Does not invent agents — requires prior KG ingest with scopes.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    workspaces = _req("GET", "/api/workspaces")
    if not workspaces:
        print("No workspaces — POST /api/context/ingest first", file=sys.stderr)
        return 1
    ws = workspaces[0]
    plan = [
        {
            "job_type": "github.create_issue",
            "agent_role": "GitHubIssueManagerAgent",
            "title": "Smoke GitHub issue",
            "requested_action": {
                "title": "[agentsuite smoke] spine write",
                "body": "Evidence-bearing GitHub write from CompanyRunWorkflow.",
            },
        },
        {
            "job_type": "gmail.send_email",
            "agent_role": "GmailCommsAgent",
            "title": "Smoke Gmail send",
            "requested_action": {
                "subject": "[agentsuite smoke] spine write",
                "body": "Evidence-bearing Gmail write from CompanyRunWorkflow.",
            },
        },
        {
            "job_type": "calendar.create_event",
            "agent_role": "CalendarSchedulerAgent",
            "title": "Smoke Calendar event",
            "requested_action": {
                "summary": "[agentsuite smoke] spine write",
                "description": "Evidence-bearing Calendar write from CompanyRunWorkflow.",
            },
        },
    ]
    run = _req(
        "POST",
        "/api/runs",
        {
            "title": "Smoke: GitHub + Gmail + Calendar",
            "objectives": ["Prove real writes with evidence + validation"],
            "workspace_ids": [ws["id"]],
            "plan": plan,
        },
    )
    print(json.dumps(run, indent=2))
    print(
        "\nGmail defaults to HIL — approve via POST /api/approvals/{id}/decide "
        "or the Approvals UI when blocked."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"API not reachable at {API}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

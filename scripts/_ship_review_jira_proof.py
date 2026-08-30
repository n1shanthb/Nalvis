"""Prove github.review_pr + jira.create_ticket via CompanyRun."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone

API = "http://127.0.0.1:8000"


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode() or "{}")


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    ws = req("GET", "/api/workspaces")[0]["id"]
    # Ensure jira scope includes SCRUM
    plan = [
        {
            "job_type": "github.review_pr",
            "agent_role": "GitHubPRReviewerAgent",
            "requested_action": {
                "pull_number": 2,
                "body": f"[agentsuite ship] review comment {stamp}",
                "event": "COMMENT",
            },
        },
        {
            "job_type": "jira.create_ticket",
            "agent_role": "JiraSyncAgent",
            "requested_action": {
                "summary": f"[agentsuite ship] {stamp}",
                "project_key": "SCRUM",
            },
        },
    ]
    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"review+jira {stamp}",
            "workspace_ids": [ws],
            "plan": plan,
            "objectives": ["PR review + Jira create"],
        },
    )
    rid = run["id"]
    print("run", rid)
    deadline = time.time() + 180
    while time.time() < deadline:
        for ap in req("GET", "/api/approvals?decision=pending"):
            if ap.get("runId") == rid:
                req("POST", f"/api/approvals/{ap['id']}/decide", {"decision": "approved"})
                print("approved", ap["id"], ap.get("jobType"))
        jobs = req("GET", f"/api/jobs?run_id={rid}")
        print([(j.get("jobType"), j.get("status"), (j.get("error") or "")[:100]) for j in jobs])
        if jobs and all(j.get("status") in ("succeeded", "failed") for j in jobs):
            break
        time.sleep(3)
    vals = [v for v in req("GET", "/api/validations") if v.get("runId") == rid]
    print("validations", [(v.get("jobType"), v.get("verdict")) for v in vals])
    for j in jobs:
        print("evidence", j.get("jobType"), j.get("evidence"))


if __name__ == "__main__":
    main()

"""Focused proof: second GitHub job type + optional Jira."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
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
    plan = [
        {
            "job_type": "github.create_or_update_workflow",
            "requested_action": {
                "file_path": ".github/workflows/agentsuite-ship-smoke.yml",
                "message": f"[ship] wf {stamp}",
            },
        }
    ]
    jira_key = (os.environ.get("SMOKE_JIRA_PROJECT_KEY") or "").strip()
    if jira_key:
        plan.append(
            {
                "job_type": "jira.create_ticket",
                "requested_action": {"summary": f"[ship] {stamp}", "project_key": jira_key},
            }
        )
    else:
        print("SMOKE_JIRA_PROJECT_KEY unset — jira skipped")

    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"github2+jira {stamp}",
            "workspace_ids": [ws],
            "plan": plan,
            "objectives": ["second github type + jira"],
        },
    )
    rid = run["id"]
    print("run", rid, "plan", [p["job_type"] for p in plan])
    deadline = time.time() + 180
    while time.time() < deadline:
        for ap in req("GET", "/api/approvals?decision=pending"):
            if ap.get("runId") == rid:
                req("POST", f"/api/approvals/{ap['id']}/decide", {"decision": "approved"})
                print("approved", ap["id"])
        jobs = req("GET", f"/api/jobs?run_id={rid}")
        print([(j.get("jobType"), j.get("status"), (j.get("error") or "")[:120]) for j in jobs])
        if jobs and all(j.get("status") in ("succeeded", "failed") for j in jobs):
            break
        time.sleep(3)
    vals = [v for v in req("GET", "/api/validations") if v.get("runId") == rid]
    print("validations", [(v.get("jobType"), v.get("verdict")) for v in vals])


if __name__ == "__main__":
    main()

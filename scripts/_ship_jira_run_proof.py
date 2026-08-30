"""CompanyRun Jira create proof after KG ingest with jira scope."""
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
    kg = {
        "company": "ShipCo",
        "products": [
            {
                "name": "Analytics",
                "repos": ["n1shanthb/analytics-resume"],
                "jira": ["SCRUM"],
                "calendars": ["primary"],
                "email_groups": ["nalvistech@gmail.com"],
                "systems": ["github", "jira", "gmail", "calendar"],
            }
        ],
    }
    req("DELETE", "/api/demo/state")
    req("POST", "/api/context/ingest", {"raw": json.dumps(kg), "source": "paste", "name": "jira-kg.json"})
    agents = req("GET", "/api/agents")
    print(
        "jira agents",
        [
            (a.get("role"), a.get("status"), a.get("systemKey"))
            for a in agents
            if "jira" in (a.get("systemKey") or "").lower() or "Jira" in (a.get("role") or "")
        ],
    )
    ws = req("GET", "/api/workspaces")[0]
    print("workspace", ws.get("id"), "jiraKeys", (ws.get("scope") or {}).get("jiraKeys") or ws.get("jiraScope"))
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"jira run {stamp}",
            "workspace_ids": [ws["id"]],
            "plan": [
                {
                    "job_type": "jira.create_ticket",
                    "requested_action": {"summary": f"[ship run] {stamp}", "project_key": "SCRUM"},
                }
            ],
            "objectives": ["jira"],
        },
    )
    rid = run["id"]
    print("run", rid)
    deadline = time.time() + 120
    jobs: list = []
    while time.time() < deadline:
        for ap in req("GET", "/api/approvals?decision=pending"):
            if ap.get("runId") == rid:
                aid = ap["id"]
                req("POST", f"/api/approvals/{aid}/decide", {"decision": "approved"})
        jobs = req("GET", f"/api/jobs?run_id={rid}")
        print([(j.get("jobType"), j.get("status"), (j.get("error") or "")[:100]) for j in jobs])
        if jobs and all(j.get("status") in ("succeeded", "failed") for j in jobs):
            break
        time.sleep(3)
    vals = [v for v in req("GET", "/api/validations") if v.get("runId") == rid]
    print("vals", [(v.get("jobType"), v.get("verdict")) for v in vals])
    for j in jobs:
        print("evidence", j.get("evidence"))


if __name__ == "__main__":
    main()

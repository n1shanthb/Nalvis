"""Targeted DoD #4 proof: create_issue + review_pr with validation PASS."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
PROOF = ROOT / "data" / "smoke_proof"
API = "http://127.0.0.1:8000"


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode() or "{}")


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proof: dict = {"stamp": stamp, "goal": "dod4_two_github_types", "ok": False}

    # Direct execute+validate first (fast feedback)
    from aip.jobs.execute import execute_job_type
    from aip.jobs.validate import validate_job

    issue = execute_job_type(
        "github.create_issue",
        {
            "owner": "n1shanthb",
            "repo": "analytics-resume",
            "title": f"[agentsuite dod4] issue {stamp}",
            "body": "DoD #4 create_issue evidence",
        },
    )
    review = execute_job_type(
        "github.review_pr",
        {
            "owner": "n1shanthb",
            "repo": "nalvis-landing",
            "pull_number": 15,
            "body": f"[agentsuite dod4] review {stamp}",
            "event": "COMMENT",
        },
    )
    proof["direct"] = {
        "create_issue": {
            "ok": issue.get("ok"),
            "evidence": issue.get("evidence"),
            "error": issue.get("error"),
            "validation": validate_job(
                job_type="github.create_issue", evidence=issue.get("evidence")
            )
            if issue.get("ok")
            else None,
        },
        "review_pr": {
            "ok": review.get("ok"),
            "evidence": review.get("evidence"),
            "error": review.get("error"),
            "validation": validate_job(
                job_type="github.review_pr", evidence=review.get("evidence")
            )
            if review.get("ok")
            else None,
        },
    }

    # CompanyRun path with both types in plan
    req("DELETE", "/api/demo/state")
    kg = {
        "company": "ShipCo",
        "products": [
            {
                "name": "Analytics",
                "repos": ["n1shanthb/analytics-resume", "n1shanthb/nalvis-landing"],
                "calendars": ["primary"],
                "email_groups": ["nalvistech@gmail.com"],
                "systems": ["github"],
            }
        ],
    }
    req("POST", "/api/context/ingest", {"raw": json.dumps(kg), "source": "paste", "name": "dod4-kg.json"})
    ws = req("GET", "/api/workspaces")[0]["id"]
    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"DoD4 github two types {stamp}",
            "workspace_ids": [ws],
            "objectives": ["Two GitHub job types"],
            "plan": [
                {
                    "job_type": "github.create_issue",
                    "requested_action": {
                        "owner": "n1shanthb",
                        "repo": "analytics-resume",
                        "title": f"[agentsuite dod4 run] {stamp}",
                        "body": "CompanyRun create_issue",
                    },
                },
                {
                    "job_type": "github.review_pr",
                    "requested_action": {
                        "owner": "n1shanthb",
                        "repo": "nalvis-landing",
                        "pull_number": 15,
                        "body": f"[agentsuite dod4 run] review {stamp}",
                        "event": "COMMENT",
                    },
                },
            ],
        },
    )
    rid = run["id"]
    proof["run_id"] = rid
    proof["temporalWorkflowId"] = run.get("temporalWorkflowId")
    deadline = time.time() + 240
    jobs: list = []
    while time.time() < deadline:
        for ap in req("GET", "/api/approvals?decision=pending"):
            if ap.get("runId") == rid:
                req("POST", f"/api/approvals/{ap['id']}/decide", {"decision": "approved"})
        jobs = req("GET", f"/api/jobs?run_id={rid}")
        if jobs and all(j.get("status") in ("succeeded", "failed") for j in jobs):
            break
        time.sleep(3)
    vals = [v for v in req("GET", "/api/validations") if v.get("runId") == rid]
    # Wait briefly for ValidationWorkflow fan-in if jobs just finished
    if jobs and len(vals) < len([j for j in jobs if j.get("status") == "succeeded"]):
        time.sleep(8)
        vals = [v for v in req("GET", "/api/validations") if v.get("runId") == rid]
    proof["jobs"] = [
        {"jobType": j.get("jobType"), "status": j.get("status"), "error": j.get("error"), "evidence": j.get("evidence")}
        for j in jobs
    ]
    proof["validations"] = [{"jobType": v.get("jobType"), "verdict": v.get("verdict")} for v in vals]
    gh_pass = {
        v.get("jobType")
        for v in vals
        if v.get("verdict") == "PASS" and str(v.get("jobType") or "").startswith("github.")
    }
    proof["ok"] = len(gh_pass) >= 2 and bool(proof["direct"]["create_issue"]["ok"]) and bool(
        proof["direct"]["review_pr"]["ok"]
    )
    PROOF.mkdir(parents=True, exist_ok=True)
    path = PROOF / f"dod4_github_{stamp}.json"
    path.write_text(json.dumps(proof, indent=2, default=str), encoding="utf-8")
    (PROOF / "dod4_github_latest.json").write_text(
        json.dumps(proof, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"ok": proof["ok"], "direct_ok": {
        "issue": proof["direct"]["create_issue"]["ok"],
        "review": proof["direct"]["review_pr"]["ok"],
        "issue_val": (proof["direct"]["create_issue"].get("validation") or {}).get("verdict"),
        "review_val": (proof["direct"]["review_pr"].get("validation") or {}).get("verdict"),
    }, "run_vals": proof["validations"], "path": str(path)}, indent=2))
    return 0 if proof["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

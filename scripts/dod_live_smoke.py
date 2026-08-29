"""End-to-end live smoke: ingest → CompanyRun → GitHub+Gmail+Calendar evidence → validation.

Writes proof JSON under data/smoke_proof/ (not synthetic — captured from live API/DB).
Requires: docker infra, API on :8000, Temporal worker with CompanyRunWorkflow.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = ROOT / "data" / "smoke_proof"
API = "http://127.0.0.1:8000"

KG = {
    "company": "SmokeCo",
    "products": [
        {
            "name": "Analytics",
            "repos": ["n1shanthb/analytics-resume"],
            "calendars": ["primary"],
            "email_groups": ["nalvistech@gmail.com"],
            "systems": ["github", "gmail", "calendar", "slack"],
        }
    ],
    "systems": ["notion"],
}


def req(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict | list:
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main() -> int:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proof: dict = {"started_at": stamp, "steps": [], "ok": False}

    try:
        health = req("GET", "/api/integrations/health")
    except urllib.error.URLError as exc:
        proof["blocker"] = f"API unreachable at {API}: {exc}"
        _write(proof, stamp)
        print(proof["blocker"], file=sys.stderr)
        return 2

    proof["integrations_health"] = health
    unhealthy = [
        i["name"]
        for i in (health.get("integrations") or [])
        if i.get("name") in ("github", "gmail", "calendar") and i.get("status") != "healthy"
    ]
    if unhealthy:
        proof["blocker"] = f"Connectors not healthy: {unhealthy}"
        _write(proof, stamp)
        print(proof["blocker"], file=sys.stderr)
        return 3

    # 1) Ingest
    doc = req("POST", "/api/context/ingest", {"raw": json.dumps(KG), "source": "paste", "name": "smoke-kg.json"})
    proof["steps"].append({"ingest": {"id": doc.get("id"), "workspaceIds": doc.get("workspaceIds")}})
    workspaces = req("GET", "/api/workspaces")
    assert isinstance(workspaces, list) and workspaces, "no workspaces after ingest"
    ws_id = workspaces[0]["id"]

    agents = req("GET", "/api/agents")
    unsupported = [a for a in agents if a.get("status") == "unsupported"]
    proof["steps"].append(
        {
            "agents": {
                "count": len(agents),
                "unsupported_systems": sorted({a.get("systemKey") for a in unsupported}),
                "executable_roles": sorted(
                    {a.get("role") for a in agents if a.get("status") != "unsupported"}
                ),
            }
        }
    )

    # Ensure Gmail HIL does not block automated smoke — still exercise HIL on a separate job if needed.
    # Prefer: keep gmail HIL on, and approve via API mid-run (proves DoD item 6).
    # For calendar/github defaults allow.

    plan = [
        {
            "job_type": "github.create_issue",
            "agent_role": "GitHubIssueManagerAgent",
            "title": "DoD smoke GitHub",
            "requested_action": {
                "title": f"[agentsuite DoD smoke] {stamp}",
                "body": "Live evidence write for goallol DoD.",
            },
        },
        {
            "job_type": "calendar.create_event",
            "agent_role": "CalendarSchedulerAgent",
            "title": "DoD smoke Calendar",
            "requested_action": {
                "summary": f"[agentsuite DoD smoke] {stamp}",
                "description": "Live evidence write for goallol DoD.",
            },
        },
        {
            "job_type": "gmail.send_email",
            "agent_role": "GmailCommsAgent",
            "title": "DoD smoke Gmail (HIL)",
            "requested_action": {
                "subject": f"[agentsuite DoD smoke] {stamp}",
                "body": "Live evidence write for goallol DoD (HIL-gated).",
            },
        },
    ]

    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"DoD smoke {stamp}",
            "objectives": ["Prove GitHub+Gmail+Calendar evidence writes"],
            "workspace_ids": [ws_id],
            "plan": plan,
        },
        timeout=60,
    )
    proof["steps"].append(
        {"start_run": {"id": run.get("id"), "temporalWorkflowId": run.get("temporalWorkflowId"), "status": run.get("status")}}
    )
    run_id = run["id"]
    if not run.get("temporalWorkflowId"):
        proof["blocker"] = "Run created without temporalWorkflowId"
        _write(proof, stamp)
        return 4

    # Poll: approve HIL when pending, wait for jobs
    deadline = time.time() + 240
    last_jobs: list = []
    while time.time() < deadline:
        approvals = req("GET", "/api/approvals?decision=pending")
        assert isinstance(approvals, list)
        for ap in approvals:
            if ap.get("runId") == run_id:
                decided = req(
                    "POST",
                    f"/api/approvals/{ap['id']}/decide",
                    {"decision": "approved"},
                )
                proof["steps"].append({"hil_approved": decided.get("id"), "jobType": decided.get("jobType")})

        jobs = req("GET", f"/api/jobs?run_id={run_id}")
        assert isinstance(jobs, list)
        last_jobs = jobs
        statuses = {j["jobType"]: j["status"] for j in jobs}
        proof["poll"] = {"statuses": statuses, "at": datetime.now(timezone.utc).isoformat()}
        if jobs and all(j["status"] in ("succeeded", "failed") for j in jobs):
            break
        # also check run status
        detail = req("GET", f"/api/runs/{run_id}")
        if detail.get("status") in ("succeeded", "failed", "partial") and jobs:
            if all(j["status"] in ("succeeded", "failed", "blocked_for_approval") for j in jobs):
                if not any(j["status"] == "blocked_for_approval" for j in jobs):
                    break
        time.sleep(3)

    validations = req("GET", "/api/validations")
    assert isinstance(validations, list)
    run_vals = [v for v in validations if v.get("runId") == run_id]

    evidence_by_system = {}
    for j in last_jobs:
        jt = j.get("jobType") or ""
        ev = j.get("evidence") or {}
        refs = ev.get("refs") if isinstance(ev, dict) else {}
        evidence_by_system[jt] = {"status": j.get("status"), "error": j.get("error"), "refs": refs}

    needed = {
        "github.create_issue": {"issue_url", "repo", "issue_number"},
        "gmail.send_email": {"message_id", "thread_id"},
        "calendar.create_event": {"calendar_id", "event_id"},
    }
    missing = []
    for jt, fields in needed.items():
        row = evidence_by_system.get(jt) or {}
        refs = row.get("refs") or {}
        if row.get("status") != "succeeded":
            missing.append(f"{jt} status={row.get('status')} error={row.get('error')}")
            continue
        lack = [f for f in fields if not refs.get(f)]
        if lack:
            missing.append(f"{jt} missing refs {lack}")

    proof["jobs"] = last_jobs
    proof["validations"] = run_vals
    proof["evidence_summary"] = evidence_by_system
    proof["run"] = req("GET", f"/api/runs/{run_id}")
    # Wait briefly for trailing validations if jobs already succeeded
    if not missing and len(run_vals) < 3:
        time.sleep(5)
        validations = req("GET", "/api/validations")
        assert isinstance(validations, list)
        run_vals = [v for v in validations if v.get("runId") == run_id]
        proof["validations"] = run_vals

    needed_types = set(needed.keys())
    verdict_types = {v.get("jobType") for v in run_vals}
    proof["ok"] = (
        len(missing) == 0
        and needed_types.issubset(verdict_types)
        and all(v.get("verdict") in ("PASS", "FAIL", "NO_EVIDENCE") for v in run_vals if v.get("jobType") in needed_types)
    )
    if missing:
        proof["blocker"] = "; ".join(missing)
    elif not proof["ok"]:
        proof["blocker"] = f"validation incomplete: have {sorted(verdict_types)} need {sorted(needed_types)}"

    path = _write(proof, stamp)
    print(json.dumps({"ok": proof["ok"], "proof": str(path), "blocker": proof.get("blocker"), "evidence_summary": evidence_by_system, "verdicts": [(v.get("jobType"), v.get("verdict")) for v in run_vals]}, indent=2))
    return 0 if proof["ok"] else 5


def _write(proof: dict, stamp: str) -> Path:
    path = PROOF_DIR / f"dod_smoke_{stamp}.json"
    path.write_text(json.dumps(proof, indent=2, default=str), encoding="utf-8")
    latest = PROOF_DIR / "latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

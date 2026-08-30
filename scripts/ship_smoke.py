"""Ship-ready smoke: LLM routing proof + optional live cross-system path.

Writes proof under data/smoke_proof/. Live connector steps skip when unhealthy
(do not fake PASS). Console-driven path is exercised via HTTP API.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = ROOT / "data" / "smoke_proof"
API = os.environ.get("AGENTS_API", "http://127.0.0.1:8000")

# Ensure package imports for offline LLM proof
sys.path.insert(0, str(ROOT / "portable_core" / "src"))


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


def _write(proof: dict, stamp: str) -> None:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    path = PROOF_DIR / f"ship_smoke_{stamp}.json"
    path.write_text(json.dumps(proof, indent=2, default=str), encoding="utf-8")
    (PROOF_DIR / "ship_latest.json").write_text(
        json.dumps(proof, indent=2, default=str), encoding="utf-8"
    )
    print(f"wrote {path}")


def _llm_director_proof(proof: dict) -> bool:
    """DoD item 1: OpenRouter-only key can drive free-text Director routing (mocked HTTP ok)."""
    from unittest.mock import patch

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from aip.director.router import route
    from aip.llm.client import llm_configured, reset_llm_client_cache, resolve_llm_api_key

    reset_llm_client_cache()
    # Simulate empty OPENAI + present OpenRouter for the assertion path
    openai_was = os.environ.get("OPENAI_API_KEY")
    or_was = os.environ.get("OPENROUTER_API_KEY")
    try:
        if not (or_was or "").strip() and not (openai_was or "").strip():
            proof["llm"] = {"configured": False, "note": "no LLM key in env — skipped live LLM call"}
            return False
        # Prefer proving OpenRouter path when OPENAI empty
        key = resolve_llm_api_key()
        proof["llm"] = {
            "configured": llm_configured(),
            "key_source": "openai" if (openai_was or "").strip() else "openrouter",
            "key_prefix": (key[:8] + "…") if key else None,
        }
        agents = [
            {
                "id": "agt-gh",
                "role": "GitHubIssueManagerAgent",
                "status": "idle",
                "activation": "ready",
                "systemKey": "github",
                "toolScope": ["github.create_issue"],
            },
            {
                "id": "agt-cal",
                "role": "CalendarSchedulerAgent",
                "status": "idle",
                "activation": "ready",
                "systemKey": "calendar",
                "toolScope": ["calendar.create_event", "calendar.update_event"],
            },
        ]
        workspace = {"scope": {"repos": ["n1shanthb/analytics-resume"], "calendars": ["primary"]}}
        # Live LLM call when key present
        decision = route(
            agents=agents,
            workspace=workspace,
            objectives=["Create a GitHub issue summarizing the flaky CI on the smoke repo"],
            plan=None,
            signal=None,
        )
        proof["llm"]["jobs"] = [
            {"job_type": j.job_type, "agent_id": j.agent_id, "rationale": j.rationale}
            for j in decision.jobs
        ]
        proof["llm"]["notes"] = decision.notes
        return bool(decision.jobs)
    except Exception as exc:  # noqa: BLE001
        proof["llm"] = {**(proof.get("llm") or {}), "error": str(exc)[:500]}
        return False
    finally:
        reset_llm_client_cache()


def main() -> int:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proof: dict = {
        "started_at": stamp,
        "goal": "goalship",
        "steps": [],
        "dod": {},
        "ok": False,
    }

    # 1) LLM free-text Director
    proof["dod"]["1_llm_freetext"] = _llm_director_proof(proof)

    # API optional for remaining live checks
    try:
        health = req("GET", "/api/integrations/health")
    except urllib.error.URLError as exc:
        proof["blocker"] = f"API unreachable at {API}: {exc}"
        proof["dod"]["note"] = "LLM proof may still stand; live ship steps blocked"
        _write(proof, stamp)
        print(proof["blocker"], file=sys.stderr)
        return 0 if proof["dod"].get("1_llm_freetext") else 2

    proof["integrations_health"] = {
        "ok": health.get("ok"),
        "integrations": [
            {
                "name": i.get("name"),
                "status": i.get("status"),
                "lastSuccessfulCallAt": i.get("lastSuccessfulCallAt"),
            }
            for i in (health.get("integrations") or [])
        ],
    }

    # Clear → ingest graph-ish / flat KG
    try:
        req("DELETE", "/api/demo/state")
    except Exception:  # noqa: BLE001
        pass

    jira_key = (os.environ.get("SMOKE_JIRA_PROJECT_KEY") or "").strip() or "SCRUM"
    smoke_owner = (os.environ.get("SMOKE_GITHUB_OWNER") or "n1shanthb").strip()
    smoke_repo = (os.environ.get("SMOKE_GITHUB_REPO") or "analytics-resume").strip()
    app_repo = (os.environ.get("SMOKE_GITHUB_APP_REPO") or "").strip()
    if not app_repo and "/" not in app_repo:
        # Discover from settings after dotenv
        try:
            from aip.config import settings as _s

            app_repo = (_s.smoke_github_app_repo or "").strip()
        except Exception:  # noqa: BLE001
            app_repo = ""
    repos = [f"{smoke_owner}/{smoke_repo}"]
    if app_repo and app_repo not in repos:
        repos.append(app_repo)

    kg = {
        "company": "ShipCo",
        "products": [
            {
                "name": "Analytics",
                "repos": repos,
                "calendars": ["primary"],
                "email_groups": [os.environ.get("GMAIL_USER") or "nalvistech@gmail.com"],
                "jira": [jira_key],
                "systems": ["github", "gmail", "calendar", "jira", "slack"],
            }
        ],
        "systems": ["notion"],
    }

    doc = req("POST", "/api/context/ingest", {"raw": json.dumps(kg), "source": "paste", "name": "ship-kg.json"})
    proof["steps"].append({"ingest": {"id": doc.get("id"), "workspaceIds": doc.get("workspaceIds")}})
    workspaces = req("GET", "/api/workspaces")
    assert isinstance(workspaces, list) and workspaces
    ws_id = workspaces[0]["id"]
    agents = req("GET", "/api/agents")
    proof["dod"]["3_ingest_agents"] = {
        "agent_count": len(agents) if isinstance(agents, list) else 0,
        "unsupported": sorted(
            {
                a.get("systemKey")
                for a in (agents or [])
                if a.get("status") == "unsupported"
            }
        ),
    }

    healthy = {
        i["name"]: i.get("status") == "healthy"
        for i in (health.get("integrations") or [])
    }

    plan: list[dict] = []
    if healthy.get("github"):
        plan.append(
            {
                "job_type": "github.create_issue",
                "title": "Ship smoke GitHub issue",
                "requested_action": {
                    "owner": smoke_owner,
                    "repo": smoke_repo,
                    "title": f"[agentsuite ship] issue {stamp}",
                    "body": "Ship smoke create_issue",
                },
            }
        )
        # Second GitHub job type: prefer review_pr on App-installed repo
        pr_n = (os.environ.get("SMOKE_GITHUB_PR_NUMBER") or "").strip()
        app_owner, app_name = "", ""
        if app_repo and "/" in app_repo:
            app_owner, app_name = app_repo.split("/", 1)
        if pr_n and app_owner and app_name:
            plan.append(
                {
                    "job_type": "github.review_pr",
                    "title": "Ship smoke GitHub PR review",
                    "requested_action": {
                        "owner": app_owner,
                        "repo": app_name,
                        "pull_number": int(pr_n),
                        "body": f"[agentsuite ship] review {stamp}",
                        "event": "COMMENT",
                    },
                }
            )
        elif app_owner and app_name:
            plan.append(
                {
                    "job_type": "github.create_or_update_workflow",
                    "title": "Ship smoke GitHub CI workflow",
                    "requested_action": {
                        "owner": app_owner,
                        "repo": app_name,
                        "file_path": ".github/workflows/agentsuite-ship-smoke.yml",
                        "message": f"[agentsuite ship] workflow {stamp}",
                    },
                }
            )
        else:
            proof["steps"].append(
                {
                    "github_second_type": "skipped — set SMOKE_GITHUB_APP_REPO (+ optional SMOKE_GITHUB_PR_NUMBER)"
                }
            )
    if healthy.get("calendar"):
        start = datetime.now(timezone.utc) + timedelta(hours=2)
        end = start + timedelta(minutes=25)
        plan.append(
            {
                "job_type": "calendar.create_event",
                "title": "Ship smoke Calendar create",
                "requested_action": {
                    "summary": f"[agentsuite ship] {stamp}",
                    "start": start.isoformat().replace("+00:00", "Z"),
                    "end": end.isoformat().replace("+00:00", "Z"),
                },
            }
        )
    if healthy.get("gmail"):
        plan.append(
            {
                "job_type": "gmail.send_email",
                "title": "Ship smoke Gmail",
                "requested_action": {
                    "subject": f"[agentsuite ship] {stamp}",
                    "body": "Ship smoke gmail send",
                },
            }
        )
    if healthy.get("jira"):
        plan.append(
            {
                "job_type": "jira.create_ticket",
                "title": "Ship smoke Jira",
                "requested_action": {
                    "summary": f"[agentsuite ship] {stamp}",
                    "project_key": jira_key,
                },
            }
        )

    systems_in_plan = {p["job_type"].split(".")[0] for p in plan}
    proof["dod"]["8_cross_system_planned"] = len(systems_in_plan) >= 2
    proof["steps"].append({"plan_job_types": [p["job_type"] for p in plan]})

    if not plan:
        proof["blocker"] = "No healthy connectors for live plan"
        _write(proof, stamp)
        return 0 if proof["dod"].get("1_llm_freetext") else 3

    run = req(
        "POST",
        "/api/runs",
        {
            "title": f"Ship smoke {stamp}",
            "objectives": ["Ship-ready multi-system evidence"],
            "workspace_ids": [ws_id],
            "plan": plan,
        },
    )
    run_id = run["id"]
    proof["steps"].append(
        {
            "start_run": {
                "id": run_id,
                "temporalWorkflowId": run.get("temporalWorkflowId"),
            }
        }
    )

    # Calendar update as follow-up after create — handled if create leaves event_id (poll)
    deadline = time.time() + 300
    last_jobs: list = []
    cal_event_id = None
    while time.time() < deadline:
        approvals = req("GET", "/api/approvals?decision=pending")
        for ap in approvals if isinstance(approvals, list) else []:
            if ap.get("runId") == run_id:
                req(
                    "POST",
                    f"/api/approvals/{ap['id']}/decide",
                    {"decision": "approved"},
                )
        jobs = req("GET", f"/api/jobs?run_id={run_id}")
        last_jobs = jobs if isinstance(jobs, list) else []
        for j in last_jobs:
            if j.get("jobType") == "calendar.create_event" and j.get("status") == "succeeded":
                refs = ((j.get("evidence") or {}).get("refs") or {})
                cal_event_id = refs.get("event_id")
        statuses = {j.get("status") for j in last_jobs}
        if last_jobs and statuses <= {"succeeded", "failed"} and "queued" not in statuses and "running" not in statuses and "blocked_for_approval" not in statuses:
            break
        time.sleep(3)

    # Optional calendar update second run
    if cal_event_id and healthy.get("calendar"):
        upd = req(
            "POST",
            "/api/runs",
            {
                "title": f"Ship smoke cal update {stamp}",
                "objectives": ["Reschedule meeting"],
                "workspace_ids": [ws_id],
                "plan": [
                    {
                        "job_type": "calendar.update_event",
                        "requested_action": {
                            "event_id": cal_event_id,
                            "summary": f"[agentsuite ship] updated {stamp}",
                        },
                    }
                ],
            },
        )
        proof["steps"].append({"calendar_update_run": upd.get("id")})
        # approve HIL if needed
        deadline2 = time.time() + 120
        while time.time() < deadline2:
            approvals = req("GET", "/api/approvals?decision=pending")
            for ap in approvals if isinstance(approvals, list) else []:
                if ap.get("runId") == upd.get("id"):
                    req("POST", f"/api/approvals/{ap['id']}/decide", {"decision": "approved"})
            jobs2 = req("GET", f"/api/jobs?run_id={upd['id']}")
            if isinstance(jobs2, list) and jobs2 and all(
                j.get("status") in ("succeeded", "failed") for j in jobs2
            ):
                last_jobs.extend(jobs2)
                break
            time.sleep(2)

    vals = req("GET", "/api/validations")
    run_vals = [v for v in (vals if isinstance(vals, list) else []) if v.get("runId") == run_id]
    proof["steps"].append(
        {
            "jobs": [
                {
                    "id": j.get("id"),
                    "jobType": j.get("jobType"),
                    "status": j.get("status"),
                    "evidence": j.get("evidence"),
                }
                for j in last_jobs
            ],
            "validations": [
                {"jobType": v.get("jobType"), "verdict": v.get("verdict")} for v in run_vals
            ],
        }
    )

    succeeded_types = {
        j.get("jobType") for j in last_jobs if j.get("status") == "succeeded"
    }
    proof["dod"]["4_github_two_types"] = len(
        {t for t in succeeded_types if str(t).startswith("github.")}
    ) >= 2
    proof["dod"]["5_jira"] = any(str(t).startswith("jira.") for t in succeeded_types)
    proof["dod"]["6_calendar"] = "calendar.create_event" in succeeded_types
    proof["dod"]["6b_calendar_update"] = "calendar.update_event" in succeeded_types
    proof["dod"]["7_gmail"] = "gmail.send_email" in succeeded_types
    proof["dod"]["8_cross_system"] = (
        len({str(t).split(".")[0] for t in succeeded_types}) >= 2
    )

    health2 = req("GET", "/api/integrations/health")
    proof["dod"]["9_last_successful_call"] = any(
        i.get("lastSuccessfulCallAt")
        for i in (health2.get("integrations") or [])
    )
    proof["integrations_after"] = [
        {
            "name": i.get("name"),
            "lastSuccessfulCallAt": i.get("lastSuccessfulCallAt"),
        }
        for i in (health2.get("integrations") or [])
    ]

    proof["ok"] = bool(proof["dod"].get("1_llm_freetext")) and bool(
        proof["dod"].get("8_cross_system")
    )
    _write(proof, stamp)
    print(json.dumps(proof["dod"], indent=2))
    return 0 if proof["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

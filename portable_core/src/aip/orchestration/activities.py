"""Temporal activities — DB + connectors (never long writes in FastAPI handlers)."""

from __future__ import annotations

from typing import Any

from temporalio import activity

from aip.db.repo import (
    append_audit,
    create_approval,
    create_job,
    create_validation,
    decide_approval,
    list_agents_api,
    transition_job,
    update_run_status,
)
from aip.db.schema import init_db
from aip.db.serializers import agent_to_api, approval_to_api, job_to_api, workspace_to_api
from aip.db.session import session_scope
from aip.director.auditor import audit_routing
from aip.director.router import route
from aip.jobs.idempotency import make_idempotency_key
from aip.jobs.validate import validate_job
from aip.kg.persist import ingest_context
from aip.policy.engine import evaluate_job_policy
from aip.runtime.agents_sdk import execute_job_via_agents_runtime


@activity.defn(name="ensure_schema")
async def ensure_schema() -> dict[str, Any]:
    init_db()
    return {"ok": True}


@activity.defn(name="ingest_kg_activity")
async def ingest_kg_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        result = ingest_context(
            session,
            raw=payload["raw"],
            source=payload.get("source") or "paste",
            name=payload.get("name"),
        )
        return result


@activity.defn(name="director_route_activity")
async def director_route_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """General catalog routing + routing auditor."""
    init_db()
    with session_scope() as session:
        from aip.db.orm import AgentRow, WorkspaceRow
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select

        ws = session.get(WorkspaceRow, payload["workspace_id"])
        if not ws:
            return {"ok": False, "error": "workspace not found", "accepted": [], "rejected": [], "notes": []}
        agents = list_agents_api(session)
        # Filter to agents that include this workspace (or Validation)
        agents_ws = [
            a
            for a in agents
            if payload["workspace_id"] in (a.get("workspaceIds") or [])
            or a.get("role") == "ValidationAgent"
        ]
        workspace = workspace_to_api(ws)
        decision = route(
            agents=agents_ws,
            workspace=workspace,
            objectives=list(payload.get("objectives") or []),
            plan=list(payload.get("plan") or []),
            signal=dict(payload.get("signal") or {}),
        )
        audited = audit_routing(decision, agents=agents_ws, workspace=workspace)

        materialized = []
        run_id = payload["run_id"]
        for pj in audited.accepted:
            key = make_idempotency_key(
                run_id=run_id,
                workspace_id=payload["workspace_id"],
                job_type=pj.job_type,
                requested_action=pj.requested_action,
            )
            job = create_job(
                session,
                run_id=run_id,
                workspace_id=payload["workspace_id"],
                job_type=pj.job_type,
                agent_id=pj.agent_id,
                requested_action=pj.requested_action,
                idempotency_key=key,
                title=pj.title or pj.job_type,
            )
            materialized.append(job_to_api(job))

        append_audit(
            session,
            run_id=run_id,
            kind="started",
            label=f"Director routed {len(materialized)} jobs "
            f"(rejected {len(audited.rejected)})",
            meta={"notes": decision.notes[:20]},
        )
        return {
            "ok": True,
            "jobs": materialized,
            "rejected": [
                {"job_type": j.job_type, "reason": reason, "agent_id": j.agent_id}
                for j, reason in audited.rejected
            ],
            "notes": decision.notes,
        }


@activity.defn(name="evaluate_policy_activity")
async def evaluate_policy_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"decision": "deny", "reason": "job not found"}
        ev = evaluate_job_policy(
            session,
            workspace_id=job.workspace_id,
            agent_id=job.agent_id,
            job_type=job.job_type,
        )
        return {"decision": ev.decision, "reason": ev.reason, "job_id": job.id}


@activity.defn(name="create_hil_approval_activity")
async def create_hil_approval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"ok": False, "error": "job not found"}
        appr = create_approval(
            session,
            job=job,
            temporal_workflow_id=payload.get("temporal_workflow_id") or "",
            intent_summary=payload.get("intent_summary")
            or f"Approve {job.job_type}: {job.requested_action}",
            diff_preview={
                "before": "",
                "after": str(job.requested_action),
            },
        )
        return {"ok": True, "approval": approval_to_api(appr)}


@activity.defn(name="execute_job_activity")
async def execute_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Real connector writes — GitHub / Gmail / Calendar / optional Jira."""
    init_db()
    job_id = payload["job_id"]
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, job_id)
        if not job:
            return {"ok": False, "error": "job not found"}
        job_type = job.job_type
        agent_id = job.agent_id
        action = dict(job.requested_action or {})
        if payload.get("edited_action") and isinstance(payload["edited_action"], dict):
            action.update(payload["edited_action"])
        transition_job(session, job_id, "running")

    from aip.db.rate_limit import check_rate_limit
    from aip.evidence.contracts import JOB_TYPE_SYSTEM
    import time

    system = JOB_TYPE_SYSTEM.get(job_type, "unknown")
    rl = check_rate_limit(key=f"integration:{system}", limit=20, window_sec=60)
    if not rl.get("ok"):
        with session_scope() as session:
            transition_job(session, job_id, "failed", error=str(rl.get("error")))
            from aip.db.repo import record_integration_call

            if system != "unknown":
                record_integration_call(
                    session, system=system, ok=False, error=str(rl.get("error"))
                )
        return {"ok": False, "error": rl.get("error")}

    t0 = time.monotonic()
    result = execute_job_via_agents_runtime(
        job_type,
        action,
        agent_role=str(payload.get("agent_role") or "SpecialistAgent"),
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    with session_scope() as session:
        from datetime import datetime, timezone

        from aip.db.orm import AgentRow, JobRow
        from aip.db.repo import record_integration_call

        if system != "unknown":
            record_integration_call(
                session,
                system=system,
                ok=bool(result.get("ok")),
                error=str(result.get("error"))[:500] if not result.get("ok") else None,
                latency_ms=latency_ms,
            )

        if result.get("ok"):
            transition_job(
                session,
                job_id,
                "succeeded",
                evidence=result.get("evidence"),
            )
            agent = session.get(AgentRow, agent_id)
            if agent:
                agent.last_active_at = datetime.now(timezone.utc)
                agent.status = "active"
        else:
            transition_job(
                session,
                job_id,
                "failed",
                error=str(result.get("error"))[:1000],
                evidence=result.get("evidence"),
            )
        job_row = session.get(JobRow, job_id)
        return {
            "ok": bool(result.get("ok")),
            "job": job_to_api(job_row) if job_row else None,
            "error": result.get("error"),
            "evidence": result.get("evidence"),
        }


@activity.defn(name="validate_job_activity")
async def validate_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        from aip.db.orm import JobRow

        job = session.get(JobRow, payload["job_id"])
        if not job:
            return {"ok": False, "error": "job not found"}
        execution_error = None
        if job.status == "failed" and job.error:
            execution_error = str(job.error)
        outcome = validate_job(
            job_type=job.job_type,
            evidence=job.evidence,
            requested_action=job.requested_action,
            execution_error=execution_error,
        )
        row = create_validation(
            session,
            job=job,
            verdict=outcome["verdict"],
            message=outcome["message"],
            reasoning=outcome["reasoning"],
            checks=outcome["checks"],
            confidence=float(outcome.get("confidence") or 0),
            evidence=outcome.get("evidence"),
        )
        from aip.db.serializers import validation_to_api

        return {"ok": True, "validation": validation_to_api(row)}


@activity.defn(name="mark_run_status_activity")
async def mark_run_status_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        update_run_status(session, payload["run_id"], payload["status"])
        return {"ok": True}


@activity.defn(name="fail_job_activity")
async def fail_job_activity(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with session_scope() as session:
        transition_job(session, payload["job_id"], "failed", error=payload.get("error") or "denied")
        return {"ok": True}


@activity.defn(name="fetch_gmail_inbound_signal_activity")
async def fetch_gmail_inbound_signal_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve Pub/Sub history → structured Director signal (facts only)."""
    from aip.tools.gmail import fetch_email, list_message_ids_since_history

    history_id = str(payload.get("history_id") or "").strip()
    message_id = str(payload.get("message_id") or "").strip()
    delivery_id = str(payload.get("delivery_id") or "").strip()

    # Explicit message (simulate / already known)
    if message_id:
        mail = fetch_email({"message_id": message_id})
        if mail.get("error"):
            return {"ok": False, "error": mail.get("error"), "signal": {}}
        signal = _gmail_signal_from_mail(mail, delivery_id=delivery_id, history_id=history_id)
        return {"ok": True, "signal": signal, "message_ids": [message_id]}

    if not history_id:
        return {"ok": False, "error": "history_id or message_id required", "signal": {}}

    # Gmail history API needs a *start* history id (previous). Callers often send the
    # notification's new historyId — try listing with it; on empty, fall back to recent inbox.
    try:
        ids, _newest = list_message_ids_since_history(history_id)
    except Exception as exc:  # noqa: BLE001
        # historyId may be too new / expired — soft-fail to recent messages
        ids = []
        hist_err = str(exc)[:300]
    else:
        hist_err = None

    if not ids:
        from aip.tools.gmail import search_emails

        recent = search_emails({"query": "in:inbox newer_than:1d", "max_results": 3})
        if recent.get("error"):
            return {
                "ok": False,
                "error": hist_err or recent.get("error"),
                "signal": {},
            }
        for row in recent.get("messages") or recent.get("results") or []:
            if isinstance(row, dict) and row.get("message_id"):
                ids.append(str(row["message_id"]))

    if not ids:
        return {
            "ok": True,
            "signal": {
                "channel": "gmail",
                "history_id": history_id,
                "delivery_id": delivery_id,
                "note": "no new messages resolved",
            },
            "message_ids": [],
            "skipped": True,
        }

    # Debounce: use the newest message as the signal
    mid = ids[-1]
    mail = fetch_email({"message_id": mid})
    if mail.get("error"):
        return {"ok": False, "error": mail.get("error"), "signal": {}}
    signal = _gmail_signal_from_mail(mail, delivery_id=delivery_id, history_id=history_id)
    return {"ok": True, "signal": signal, "message_ids": ids}


def _gmail_signal_from_mail(
    mail: dict[str, Any], *, delivery_id: str = "", history_id: str = ""
) -> dict[str, Any]:
    body = str(mail.get("body") or "")
    snippet = str(mail.get("snippet") or body[:500])
    return {
        "channel": "gmail",
        "subject": mail.get("subject") or "",
        "from": mail.get("from") or "",
        "to": mail.get("to") or "",
        "snippet": snippet,
        "body_summary": body[:1500] if body else snippet,
        "thread_id": mail.get("thread_id") or "",
        "message_id": mail.get("message_id") or "",
        "delivery_id": delivery_id,
        "history_id": history_id,
    }


@activity.defn(name="start_company_run_from_signal_activity")
async def start_company_run_from_signal_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist run + start CompanyRunWorkflow with Director signal (no long Google I/O here)."""
    from aip.config import settings
    from aip.db.orm import RunRow
    from aip.db.repo import create_run, list_workspaces_api, set_run_workflow
    from aip.orchestration.workflows import CompanyRunWorkflow
    from sqlalchemy import select
    from temporalio.client import Client

    init_db()
    signal = dict(payload.get("signal") or {})
    objectives = list(payload.get("objectives") or [])
    if not objectives and signal.get("subject"):
        objectives = [
            f"Inbound {signal.get('channel') or 'signal'}: {signal.get('subject')}"
        ]

    delivery_id = str(signal.get("delivery_id") or "").strip()
    thread_id = str(signal.get("thread_id") or "").strip()

    with session_scope() as session:
        # Idempotent / debounce: same Pub/Sub delivery_id or recent same thread
        if delivery_id:
            recent = session.scalars(
                select(RunRow).order_by(RunRow.created_at.desc()).limit(40)
            ).all()
            for row in recent:
                sig = row.signal if isinstance(row.signal, dict) else {}
                if str(sig.get("delivery_id") or "") == delivery_id and row.temporal_workflow_id:
                    return {
                        "ok": True,
                        "deduped": True,
                        "run_id": row.id,
                        "temporal_workflow_id": row.temporal_workflow_id,
                        "signal": signal,
                    }
        if thread_id:
            recent = session.scalars(
                select(RunRow).order_by(RunRow.created_at.desc()).limit(20)
            ).all()
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            for row in recent:
                if row.created_at and row.created_at.replace(tzinfo=timezone.utc) < cutoff:
                    continue
                sig = row.signal if isinstance(row.signal, dict) else {}
                if (
                    str(sig.get("thread_id") or "") == thread_id
                    and str(sig.get("channel") or "") == "gmail"
                    and row.status in ("queued", "running", "succeeded", "partial")
                    and row.temporal_workflow_id
                ):
                    return {
                        "ok": True,
                        "deduped": True,
                        "reason": "thread_debounce",
                        "run_id": row.id,
                        "temporal_workflow_id": row.temporal_workflow_id,
                        "signal": signal,
                    }

        ws_ids = list(payload.get("workspace_ids") or [])
        if not ws_ids:
            from aip.director.auditor import extra_github_repos_outside_kg

            all_ws = list_workspaces_api(session)
            repo = str(signal.get("repo") or "").strip().lower()
            if repo:
                matched = [
                    w["id"]
                    for w in all_ws
                    if repo
                    in [str(r).lower() for r in ((w.get("scope") or {}).get("repos") or [])]
                ]
                if matched:
                    ws_ids = matched
                elif repo in extra_github_repos_outside_kg():
                    # Outside-KG smoke/app repo: bind to one workspace only.
                    # Fan-out to every product caused duplicate HIL + duplicate PR reviews.
                    ws_ids = [all_ws[0]["id"]] if all_ws else []
                else:
                    # Unscoped github repo with no allowlist — fail closed (no cross-product writes).
                    ws_ids = []
            else:
                ws_ids = [w["id"] for w in all_ws]
        if not ws_ids:
            if str(signal.get("repo") or "").strip():
                return {
                    "ok": False,
                    "error": (
                        f"No workspace scope matches repo {signal.get('repo')!r} "
                        "(and not on smoke/app allowlist)"
                    ),
                }
            return {"ok": False, "error": "No workspaces — ingest KG first"}
        title = str(
            payload.get("title")
            or (objectives[0] if objectives else "Inbound signal run")
        )
        run = create_run(
            session,
            title=title[:500],
            objectives=objectives,
            workspace_ids=ws_ids,
            plan=list(payload.get("plan") or []),
            signal=signal,
        )
        run_id = run.id

    workflow_id = f"company-run-{run_id}"
    try:
        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        await client.start_workflow(
            CompanyRunWorkflow.run,
            {
                "run_id": run_id,
                "workspace_ids": ws_ids,
                "objectives": objectives,
                "plan": list(payload.get("plan") or []),
                "signal": signal,
            },
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as exc:  # noqa: BLE001
        with session_scope() as session:
            r = session.get(RunRow, run_id)
            if r:
                r.status = "failed"
        return {"ok": False, "error": str(exc), "run_id": run_id}

    with session_scope() as session:
        set_run_workflow(session, run_id, workflow_id)
    return {"ok": True, "run_id": run_id, "temporal_workflow_id": workflow_id, "signal": signal}


@activity.defn(name="normalize_github_webhook_signal_activity")
async def normalize_github_webhook_signal_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn a GitHub webhook envelope into a Director signal (facts only)."""
    event = str(payload.get("event") or "").strip().lower()
    action = str(payload.get("action") or "").strip().lower()
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    delivery_id = str(payload.get("delivery_id") or "").strip()

    repo = ""
    if isinstance(body.get("repository"), dict):
        repo = str(body["repository"].get("full_name") or "").strip()

    pr = body.get("pull_request") if isinstance(body.get("pull_request"), dict) else {}
    issue = body.get("issue") if isinstance(body.get("issue"), dict) else {}

    pr_number = pr.get("number")
    issue_number = issue.get("number") if not pr else None
    title = str(pr.get("title") or issue.get("title") or "").strip()
    html_url = str(pr.get("html_url") or issue.get("html_url") or "").strip()
    sender = ""
    if isinstance(body.get("sender"), dict):
        sender = str(body["sender"].get("login") or "").strip()

    subject = f"GitHub {event}.{action or 'event'}"
    if repo:
        subject += f" on {repo}"
    if pr_number is not None:
        subject += f" PR #{pr_number}"
    elif issue_number is not None:
        subject += f" issue #{issue_number}"
    if title:
        subject += f": {title[:120]}"

    snippet_parts = [
        f"event={event}",
        f"action={action}",
        f"repo={repo}",
    ]
    if pr_number is not None:
        snippet_parts.append(f"pull_number={pr_number}")
    if issue_number is not None:
        snippet_parts.append(f"issue_number={issue_number}")
    if html_url:
        snippet_parts.append(f"url={html_url}")
    if sender:
        snippet_parts.append(f"sender={sender}")

    signal: dict[str, Any] = {
        "channel": "github",
        "event": event,
        "action": action,
        "repo": repo,
        "pull_number": pr_number,
        "issue_number": issue_number,
        "title": title,
        "html_url": html_url,
        "sender": sender,
        "subject": subject,
        "snippet": "; ".join(snippet_parts),
        "body_summary": str(pr.get("body") or issue.get("body") or "")[:1500],
        "delivery_id": delivery_id,
        "thread_id": html_url or f"{repo}:{event}:{pr_number or issue_number or action}",
    }

    # Event-family → catalog job from webhook facts (not scenario trees).
    # Pin owner/repo/pull_number so Director scope enrichment cannot overwrite
    # with a different workspace repo list.
    if event == "pull_request" and pr_number is not None and repo:
        owner = ""
        repo_name = ""
        if isinstance(body.get("repository"), dict):
            repo_obj = body["repository"]
            if isinstance(repo_obj.get("owner"), dict):
                owner = str(repo_obj["owner"].get("login") or "").strip()
            repo_name = str(repo_obj.get("name") or "").strip()
        if (not owner or not repo_name) and "/" in repo:
            owner, repo_name = repo.split("/", 1)
        requested_action: dict[str, Any] = {
            "owner": owner,
            "repo": repo_name,
            "repo_full": repo,
            "pull_number": pr_number,
        }
        if title:
            requested_action["title"] = title
        if html_url:
            requested_action["pr_url"] = html_url
        signal["requested_jobs"] = [
            {
                "job_type": "github.review_pr",
                "requested_action": requested_action,
                "rationale": "GitHub pull_request webhook facts",
                "title": title or f"Review PR #{pr_number}",
            }
        ]

    elif event == "issues" and issue_number is not None and repo:
        owner = ""
        repo_name = ""
        if isinstance(body.get("repository"), dict):
            repo_obj = body["repository"]
            if isinstance(repo_obj.get("owner"), dict):
                owner = str(repo_obj["owner"].get("login") or "").strip()
            repo_name = str(repo_obj.get("name") or "").strip()
        if (not owner or not repo_name) and "/" in repo:
            owner, repo_name = repo.split("/", 1)
        issue_action: dict[str, Any] = {
            "owner": owner,
            "repo": repo_name,
            "repo_full": repo,
            "issue_number": issue_number,
        }
        if title:
            issue_action["title"] = title
        if html_url:
            issue_action["issue_url"] = html_url
        signal["requested_jobs"] = [
            {
                "job_type": "github.comment_issue",
                "requested_action": issue_action,
                "rationale": "GitHub issues webhook facts (ack/triage comment, not duplicate create)",
                "title": title or f"Comment on issue #{issue_number}",
            }
        ]

    return {"ok": True, "signal": signal, "objectives": [subject]}


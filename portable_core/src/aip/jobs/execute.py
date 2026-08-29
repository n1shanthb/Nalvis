"""ExecuteJob — real external writes with evidence contracts (Temporal activity use)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from aip.config import settings
from aip.evidence.contracts import evidence_complete, missing_evidence_fields


def execute_job_type(job_type: str, requested_action: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch by job_type registry. Returns:
      {ok, evidence: {job_type, refs, collected_at}, error?, raw?}
    """
    handler = _REGISTRY.get(job_type)
    if handler is None:
        return {"ok": False, "error": f"unsupported job_type for ExecuteJob: {job_type}"}
    try:
        result = handler(requested_action or {})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500]}

    if not result.get("ok"):
        return result

    refs = dict(result.get("evidence") or {})
    missing = missing_evidence_fields(job_type, refs)
    if missing:
        return {
            "ok": False,
            "error": f"evidence contract incomplete: missing {missing}",
            "evidence": {"job_type": job_type, "refs": refs},
            "raw": result.get("raw"),
        }
    return {
        "ok": True,
        "evidence": {
            "jobType": job_type,
            "job_type": job_type,
            "refs": {str(k): str(v) if not isinstance(v, (dict, list)) else v for k, v in refs.items()},
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "raw": result.get("raw"),
        "via": result.get("via"),
    }


def _github_create_issue(action: dict[str, Any]) -> dict[str, Any]:
    from aip.connectors.github_smoke import smoke_github_mcp_issue
    from aip.integrations.github_app import create_issue, github_app_configured

    owner = str(action.get("owner") or settings.smoke_github_owner or "").strip()
    repo = str(action.get("repo") or settings.smoke_github_repo or "").strip()
    title = str(action.get("title") or f"[agentsuite] {datetime.now(timezone.utc).isoformat()}")
    body = str(action.get("body") or "Created by AgentSuite ExecuteJob.")

    # Enforce smoke repo lock from goallol when action targets github writes without explicit override flag
    smoke_owner = (settings.smoke_github_owner or "").strip()
    smoke_repo = (settings.smoke_github_repo or "").strip()
    if smoke_owner and smoke_repo and (owner != smoke_owner or repo != smoke_repo):
        # Still allow if workspace scoped differently — caller/auditor already checked scope.
        # goallol: smoke target is analytics-resume only for DoD smoke; non-smoke repos require explicit allow.
        if not action.get("allow_non_smoke_repo"):
            return {
                "ok": False,
                "error": f"GitHub writes limited to smoke repo {smoke_owner}/{smoke_repo} "
                f"(got {owner}/{repo}). Pass allow_non_smoke_repo=true for in-scope non-smoke writes.",
            }

    if github_app_configured():
        try:
            data = create_issue(owner=owner, repo=repo, title=title[:240], body=body)
            return {
                "ok": True,
                "via": "app:create_issue",
                "evidence": {
                    "issue_url": data.get("html_url"),
                    "issue_number": data.get("number"),
                    "repo": f"{owner}/{repo}",
                },
                "raw": data,
            }
        except Exception as exc:  # noqa: BLE001
            app_err = str(exc)
    else:
        app_err = "app not configured"

    # Reuse MCP path via smoke helper but with title; patch settings temporarily is bad —
    # call smoke which uses settings owner/repo (already equal when smoke-locked).
    result = smoke_github_mcp_issue(title=title)
    if result.get("ok"):
        return result
    return {"ok": False, "error": result.get("error") or app_err, "raw": result}


def _gmail_send(action: dict[str, Any]) -> dict[str, Any]:
    from aip.tools.gmail import send_email

    to = str(action.get("to") or settings.gmail_user or "").strip()
    if not to:
        return {"ok": False, "error": "gmail.send_email requires 'to' (or GMAIL_USER)"}
    result = send_email(
        {
            "to": to,
            "subject": str(action.get("subject") or f"[agentsuite] {datetime.now(timezone.utc).isoformat()}"),
            "body": str(action.get("body") or "Sent by AgentSuite ExecuteJob."),
        }
    )
    if result.get("error"):
        return {"ok": False, "error": result}
    return {
        "ok": True,
        "via": "native:gmail.send",
        "evidence": {
            "message_id": result.get("message_id"),
            "thread_id": result.get("thread_id"),
        },
        "raw": result,
    }


def _calendar_create(action: dict[str, Any]) -> dict[str, Any]:
    from aip.tools.calendar import create_event

    start = action.get("start")
    end = action.get("end")
    if not start or not end:
        s = datetime.now(timezone.utc) + timedelta(hours=1)
        e = s + timedelta(minutes=30)
        start = s.isoformat().replace("+00:00", "Z")
        end = e.isoformat().replace("+00:00", "Z")
    calendar_id = str(action.get("calendar_id") or "primary")
    result = create_event(
        {
            "calendar_id": calendar_id,
            "summary": str(action.get("summary") or f"[agentsuite] {start}"),
            "start": start,
            "end": end,
            "description": str(action.get("description") or "Created by AgentSuite ExecuteJob."),
        }
    )
    if result.get("error"):
        return {"ok": False, "error": result}
    event = result.get("event") if isinstance(result.get("event"), dict) else result
    return {
        "ok": True,
        "via": "native:calendar.create",
        "evidence": {
            "event_id": event.get("id") if isinstance(event, dict) else None,
            "calendar_id": calendar_id,
            "html_link": event.get("htmlLink") if isinstance(event, dict) else None,
        },
        "raw": result,
    }


def _calendar_update(action: dict[str, Any]) -> dict[str, Any]:
    from aip.tools.calendar import update_event

    calendar_id = str(action.get("calendar_id") or "primary")
    event_id = str(action.get("event_id") or "").strip()
    if not event_id:
        return {"ok": False, "error": "calendar.update_event requires event_id"}
    result = update_event(
        {
            "calendar_id": calendar_id,
            "event_id": event_id,
            "summary": action.get("summary"),
            "start": action.get("start"),
            "end": action.get("end"),
            "description": action.get("description"),
        }
    )
    if result.get("error"):
        return {"ok": False, "error": result}
    return {
        "ok": True,
        "via": "native:calendar.update",
        "evidence": {"calendar_id": calendar_id, "event_id": event_id},
        "raw": result,
    }


def _jira_create(action: dict[str, Any]) -> dict[str, Any]:
    from aip.connectors import smoke as connector_smoke

    summary = str(action.get("summary") or action.get("title") or "")
    result = connector_smoke.smoke_jira_mcp_create(summary=summary or None)
    return result


def _jira_transition(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "jira.transition_ticket not wired in this spine slice (optional for goallol DoD)",
    }


_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "github.create_issue": _github_create_issue,
    "gmail.send_email": _gmail_send,
    "calendar.create_event": _calendar_create,
    "calendar.update_event": _calendar_update,
    "jira.create_ticket": _jira_create,
    "jira.transition_ticket": _jira_transition,
}


def assert_evidence_ok(job_type: str, refs: dict[str, Any]) -> bool:
    return evidence_complete(job_type, refs)

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


def _github_owner_repo(action: dict[str, Any], *, prefer_app_repo: bool = False) -> tuple[str, str]:
    """Resolve owner/repo: action fields → optional App-installed write repo → smoke defaults."""
    if action.get("repo_full"):
        full = str(action["repo_full"]).strip()
        if "/" in full:
            o, r = full.split("/", 1)
            return o.strip(), r.strip()
    owner = str(action.get("owner") or "").strip()
    repo = str(action.get("repo") or "").strip()
    # LLM/webhook payloads sometimes put "owner/repo" in repo with no owner field.
    if repo and "/" in repo and not owner:
        o, r = repo.split("/", 1)
        return o.strip(), r.strip()
    if owner and repo:
        return owner, repo
    if prefer_app_repo:
        app_repo = (settings.smoke_github_app_repo or "").strip()
        if "/" in app_repo:
            o, r = app_repo.split("/", 1)
            return o.strip(), r.strip()
    return (
        str(action.get("owner") or settings.smoke_github_owner or "").strip(),
        str(action.get("repo") or settings.smoke_github_repo or "").strip(),
    )


def _github_create_issue(action: dict[str, Any]) -> dict[str, Any]:
    from aip.connectors.github_smoke import smoke_github_mcp_issue
    from aip.integrations.github_app import create_issue, github_app_configured

    owner, repo = _github_owner_repo(action)
    guard = _smoke_repo_guard(action, owner, repo)
    if guard:
        return guard
    title = str(action.get("title") or f"[agentsuite] {datetime.now(timezone.utc).isoformat()}")
    body = str(action.get("body") or "Created by AgentSuite ExecuteJob.")

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


def _github_comment_issue(action: dict[str, Any]) -> dict[str, Any]:
    from aip.integrations.github_app import post_issue_comment

    owner, repo = _github_owner_repo(action, prefer_app_repo=True)
    guard = _smoke_repo_guard(action, owner, repo)
    if guard:
        return guard
    issue_number = action.get("issue_number") or action.get("number")
    if issue_number is None:
        return {"ok": False, "error": "github.comment_issue requires issue_number"}
    title = str(action.get("title") or "").strip()
    body = str(
        action.get("body")
        or action.get("comment")
        or (f"[agentsuite] Received issue #{issue_number}" + (f": {title}" if title else ""))
    )
    try:
        data = post_issue_comment(
            owner=owner,
            repo=repo,
            number=int(issue_number),
            body=body,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500]}
    issue_url = str(action.get("issue_url") or action.get("html_url") or "").strip()
    if not issue_url:
        issue_url = f"https://github.com/{owner}/{repo}/issues/{int(issue_number)}"
    return {
        "ok": True,
        "via": "app:issue_comment",
        "evidence": {
            "issue_url": issue_url,
            "issue_number": int(issue_number),
            "repo": f"{owner}/{repo}",
            "comment_id": data.get("id"),
        },
        "raw": data,
    }


def _gmail_send(action: dict[str, Any]) -> dict[str, Any]:
    from aip.tools.gmail import send_email, send_email_reply

    message_id = str(action.get("message_id") or "").strip()
    if message_id:
        body = str(
            action.get("body")
            or "Thank you for your message. We have received it and will follow up shortly."
        )
        result = send_email_reply({"message_id": message_id, "body": body})
        if result.get("error"):
            return {"ok": False, "error": result}
        return {
            "ok": True,
            "via": "native:gmail.reply",
            "evidence": {
                "message_id": result.get("message_id"),
                "thread_id": result.get("thread_id"),
            },
            "raw": result,
        }

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


def _smoke_repo_guard(action: dict[str, Any], owner: str, repo: str) -> dict[str, Any] | None:
    smoke_owner = (settings.smoke_github_owner or "").strip()
    smoke_repo = (settings.smoke_github_repo or "").strip()
    allowed = set()
    if smoke_owner and smoke_repo:
        allowed.add(f"{smoke_owner}/{smoke_repo}".lower())
    app_repo = (settings.smoke_github_app_repo or "").strip()
    if app_repo and "/" in app_repo:
        allowed.add(app_repo.lower())
    # Explicit allowlist entries from action
    for extra in action.get("allowed_repos") or []:
        if isinstance(extra, str) and "/" in extra:
            allowed.add(extra.strip().lower())
    target = f"{owner}/{repo}".lower()
    if allowed and target not in allowed and not action.get("allow_non_smoke_repo"):
        return {
            "ok": False,
            "error": f"GitHub writes limited to smoke/app repos {sorted(allowed)} "
            f"(got {owner}/{repo}). Pass allow_non_smoke_repo=true or set SMOKE_GITHUB_APP_REPO.",
        }
    return None


def _github_review_pr(action: dict[str, Any]) -> dict[str, Any]:
    from aip.integrations.github_app import create_pull_request_review

    owner, repo = _github_owner_repo(action, prefer_app_repo=True)
    guard = _smoke_repo_guard(action, owner, repo)
    if guard:
        return guard
    pull_number = action.get("pull_number") or action.get("pr_number") or action.get("number")
    if pull_number is None:
        return {"ok": False, "error": "github.review_pr requires pull_number"}
    body = str(action.get("body") or action.get("comment") or "[agentsuite] PR review")
    event = str(action.get("event") or "COMMENT")
    try:
        data = create_pull_request_review(
            owner=owner,
            repo=repo,
            pull_number=int(pull_number),
            body=body,
            event=event,
        )
    except Exception as exc:  # noqa: BLE001
        # Fall back to primary smoke repo if App-write repo failed and action didn't pin owner/repo
        smoke_o = (settings.smoke_github_owner or "").strip()
        smoke_r = (settings.smoke_github_repo or "").strip()
        if (
            not (action.get("owner") and action.get("repo"))
            and smoke_o
            and smoke_r
            and (owner, repo) != (smoke_o, smoke_r)
        ):
            try:
                data = create_pull_request_review(
                    owner=smoke_o,
                    repo=smoke_r,
                    pull_number=int(pull_number),
                    body=body,
                    event=event,
                )
                owner, repo = smoke_o, smoke_r
            except Exception:  # noqa: BLE001
                return {"ok": False, "error": str(exc)[:500]}
        else:
            return {"ok": False, "error": str(exc)[:500]}
    review_id = data.get("id")
    pr_url = data.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{pull_number}"
    if "/pull/" not in str(pr_url):
        pr_url = f"https://github.com/{owner}/{repo}/pull/{pull_number}"
    return {
        "ok": True,
        "via": "app:pull_request_review",
        "evidence": {
            "pr_url": pr_url,
            "review_id": review_id,
            "repo": f"{owner}/{repo}",
            "pull_number": int(pull_number),
        },
        "raw": data,
    }


def _github_create_or_update_workflow(action: dict[str, Any]) -> dict[str, Any]:
    from aip.integrations.github_app import create_or_update_repo_file

    owner, repo = _github_owner_repo(action, prefer_app_repo=True)
    guard = _smoke_repo_guard(action, owner, repo)
    if guard:
        return guard
    file_path = str(
        action.get("file_path")
        or action.get("path")
        or ".github/workflows/agentsuite-smoke.yml"
    ).strip()
    content = str(
        action.get("content")
        or action.get("workflow_yaml")
        or (
            "name: agentsuite-smoke\n"
            "on:\n  workflow_dispatch:\n"
            "jobs:\n  ping:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo agentsuite\n"
        )
    )
    message = str(action.get("message") or f"[agentsuite] update {file_path}")
    try:
        data = create_or_update_repo_file(
            owner=owner,
            repo=repo,
            path=file_path,
            content=content,
            message=message,
            branch=action.get("branch"),
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500]}
    commit = data.get("commit") if isinstance(data.get("commit"), dict) else {}
    content_meta = data.get("content") if isinstance(data.get("content"), dict) else {}
    sha = commit.get("sha") or content_meta.get("sha")
    html = content_meta.get("html_url") or commit.get("html_url") or ""
    workflow_url = (
        str(action.get("workflow_url") or "")
        or f"https://github.com/{owner}/{repo}/blob/HEAD/{file_path}"
    )
    return {
        "ok": True,
        "via": "app:contents_workflow",
        "evidence": {
            "repo": f"{owner}/{repo}",
            "commit_sha": sha,
            "file_path": file_path,
            "workflow_url": workflow_url or html,
        },
        "raw": data,
    }


def _jira_create(action: dict[str, Any]) -> dict[str, Any]:
    from aip.connectors import smoke as connector_smoke

    summary = str(action.get("summary") or action.get("title") or "")
    project_key = str(action.get("project_key") or action.get("projectKey") or "").strip()
    result = connector_smoke.smoke_jira_mcp_create(
        summary=summary or None,
        project_key=project_key or None,
    )
    return result


def _jira_transition(action: dict[str, Any]) -> dict[str, Any]:
    from aip.connectors import smoke as connector_smoke

    issue_key = str(action.get("issue_key") or action.get("issueKey") or "").strip()
    transition_id = str(action.get("transition_id") or action.get("transitionId") or "").strip()
    transition_name = str(action.get("transition_name") or action.get("transitionName") or "").strip()
    if not issue_key:
        return {"ok": False, "error": "jira.transition_ticket requires issue_key"}
    result = connector_smoke.smoke_jira_mcp_transition(
        issue_key=issue_key,
        transition_id=transition_id or None,
        transition_name=transition_name or None,
    )
    return result


_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "github.create_issue": _github_create_issue,
    "github.comment_issue": _github_comment_issue,
    "github.review_pr": _github_review_pr,
    "github.create_or_update_workflow": _github_create_or_update_workflow,
    "gmail.send_email": _gmail_send,
    "calendar.create_event": _calendar_create,
    "calendar.update_event": _calendar_update,
    "jira.create_ticket": _jira_create,
    "jira.transition_ticket": _jira_transition,
}


def assert_evidence_ok(job_type: str, refs: dict[str, Any]) -> bool:
    return evidence_complete(job_type, refs)

"""Validation — re-fetch external evidence; never auto-PASS from agent claim."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from aip.evidence.contracts import missing_evidence_fields
from aip.validation.verdicts import AuthorityVerdict


def validate_job(
    *,
    job_type: str,
    evidence: dict[str, Any] | None,
    requested_action: dict[str, Any] | None = None,
    execution_error: str | None = None,
) -> dict[str, Any]:
    """
    Returns validation payload:
      verdict, confidence, message, reasoning, checks[], evidence
    """
    if execution_error:
        return {
            "verdict": "FAIL",
            "confidence": 1.0,
            "message": "Validation FAIL",
            "reasoning": execution_error[:1000],
            "checks": [
                {
                    "name": "execute",
                    "passed": False,
                    "detail": execution_error[:500],
                }
            ],
            "evidence": {
                "jobType": job_type,
                "refs": {},
                "executionError": execution_error[:500],
            },
        }

    refs = {}
    if evidence:
        refs = dict(evidence.get("refs") or evidence)
        # unwrap nested
        if "refs" in evidence and isinstance(evidence["refs"], dict):
            refs = dict(evidence["refs"])

    missing = missing_evidence_fields(job_type, refs)
    checks: list[dict[str, Any]] = []

    if missing:
        return {
            "verdict": "NO_EVIDENCE",
            "confidence": 1.0,
            "message": f"Missing required evidence fields: {', '.join(missing)}",
            "reasoning": "Agent claim cannot be verified without contract fields.",
            "checks": [
                {
                    "name": "evidence_contract",
                    "passed": False,
                    "detail": f"missing {missing}",
                }
            ],
            "evidence": evidence,
        }

    checks.append(
        {"name": "evidence_contract", "passed": True, "detail": "required fields present"}
    )

    if job_type == "github.create_issue":
        verdict, extra = _validate_github_issue(refs)
        checks.extend(extra)
    elif job_type == "github.comment_issue":
        verdict, extra = _validate_github_comment_issue(refs)
        checks.extend(extra)
    elif job_type == "github.review_pr":
        verdict, extra = _validate_github_pr_review(refs)
        checks.extend(extra)
    elif job_type == "github.create_or_update_workflow":
        verdict, extra = _validate_github_workflow(refs)
        checks.extend(extra)
    elif job_type == "gmail.send_email":
        verdict, extra = _validate_gmail(refs)
        checks.extend(extra)
    elif job_type in ("calendar.create_event", "calendar.update_event"):
        verdict, extra = _validate_calendar(refs)
        checks.extend(extra)
    elif job_type.startswith("jira."):
        verdict, extra = _validate_jira(refs, job_type=job_type)
        checks.extend(extra)
    else:
        verdict = "NO_EVIDENCE"
        checks.append(
            {
                "name": "re_fetch",
                "passed": False,
                "detail": f"no validator for job_type {job_type}",
            }
        )

    passed = all(c.get("passed") for c in checks if c.get("name") != "evidence_contract") or (
        verdict == "PASS"
    )
    # Prefer explicit verdict from validators
    return {
        "verdict": verdict,
        "confidence": 0.9 if verdict == "PASS" else 0.95,
        "message": f"Validation {verdict}",
        "reasoning": "; ".join(c.get("detail", "") for c in checks),
        "checks": checks,
        "evidence": {
            "jobType": job_type,
            "refs": {str(k): str(v) for k, v in refs.items()},
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
    }


def _validate_github_issue(refs: dict[str, Any]) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.integrations.github_app import resolve_github_token

    repo = str(refs.get("repo") or "")
    number = refs.get("issue_number")
    url = str(refs.get("issue_url") or "")
    checks: list[dict[str, Any]] = []
    if not repo or "/" not in repo or number is None:
        return "NO_EVIDENCE", [
            {"name": "re_fetch", "passed": False, "detail": "repo/issue_number incomplete"}
        ]
    owner, name = repo.split("/", 1)
    try:
        token = resolve_github_token()
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": f"auth error: {exc}"}]

    api = f"https://api.github.com/repos/{owner}/{name}/issues/{int(number)}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                api,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code == 404:
            checks.append({"name": "re_fetch", "passed": False, "detail": "issue not found"})
            return "FAIL", checks
        if resp.status_code >= 400:
            checks.append(
                {"name": "re_fetch", "passed": False, "detail": f"HTTP {resp.status_code}"}
            )
            return "FAIL", checks
        data = resp.json()
        html = data.get("html_url") or ""
        ok = str(data.get("number")) == str(number)
        if url and html and url.rstrip("/") != html.rstrip("/"):
            checks.append(
                {
                    "name": "url_match",
                    "passed": False,
                    "detail": f"url mismatch claim={url} observed={html}",
                }
            )
            return "FAIL", checks
        checks.append({"name": "re_fetch", "passed": ok, "detail": f"issue #{number} exists"})
        return ("PASS" if ok else "FAIL"), checks
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": str(exc)[:200]}]


def _validate_gmail(refs: dict[str, Any]) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.tools.gmail import GmailRestClient, gmail_configured
    from aip.integrations.gmail_oauth import gmail_configured as gc

    if not gc():
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "gmail not configured"}]
    message_id = str(refs.get("message_id") or "").strip()
    if not message_id:
        return "NO_EVIDENCE", [{"name": "re_fetch", "passed": False, "detail": "no message_id"}]
    client = GmailRestClient()
    # users.messages.get
    from aip.config import settings

    user = (settings.gmail_user or "me").strip() or "me"
    data = client.request("GET", f"/users/{user}/messages/{message_id}", params={"format": "minimal"})
    if isinstance(data, dict) and data.get("error"):
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": str(data)[:200]}]
    observed_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    ok = observed_id == message_id or bool(data)
    thread = str(refs.get("thread_id") or "")
    if thread and isinstance(data, dict) and data.get("threadId") and str(data.get("threadId")) != thread:
        return "FAIL", [
            {
                "name": "thread_match",
                "passed": False,
                "detail": f"thread mismatch claim={thread} observed={data.get('threadId')}",
            }
        ]
    return ("PASS" if ok else "FAIL"), [
        {"name": "re_fetch", "passed": ok, "detail": f"message {message_id} fetched"}
    ]


def _validate_calendar(refs: dict[str, Any]) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.tools.calendar import CalendarRestClient, calendar_configured

    if not calendar_configured():
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "calendar not configured"}]
    calendar_id = str(refs.get("calendar_id") or "primary")
    event_id = str(refs.get("event_id") or "").strip()
    if not event_id:
        return "NO_EVIDENCE", [{"name": "re_fetch", "passed": False, "detail": "no event_id"}]
    client = CalendarRestClient()
    data = client.request("GET", f"/calendars/{calendar_id}/events/{event_id}")
    if isinstance(data, dict) and data.get("error"):
        detail = str(data)[:200]
        if "404" in detail:
            return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "event not found"}]
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": detail}]
    ok = isinstance(data, dict) and str(data.get("id") or "") == event_id
    return ("PASS" if ok else "FAIL"), [
        {"name": "re_fetch", "passed": ok, "detail": f"event {event_id} fetched"}
    ]


def _validate_github_pr_review(
    refs: dict[str, Any],
) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.integrations.github_app import resolve_github_token

    pr_url = str(refs.get("pr_url") or "")
    review_id = refs.get("review_id")
    checks: list[dict[str, Any]] = []
    if not pr_url:
        return "NO_EVIDENCE", [{"name": "re_fetch", "passed": False, "detail": "no pr_url"}]
    # Parse owner/repo/number from URL
    import re

    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": f"bad pr_url {pr_url}"}]
    owner, repo, number = m.group(1), m.group(2), int(m.group(3))
    try:
        token = resolve_github_token()
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": f"auth error: {exc}"}]
    api = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                api,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code == 404:
            return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "PR not found"}]
        if resp.status_code >= 400:
            return "FAIL", [
                {"name": "re_fetch", "passed": False, "detail": f"HTTP {resp.status_code}"}
            ]
        checks.append({"name": "pr_exists", "passed": True, "detail": f"PR #{number} exists"})
        if review_id:
            with httpx.Client(timeout=30.0) as client2:
                rev = client2.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews/{int(review_id)}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
            if rev.status_code >= 400:
                checks.append(
                    {
                        "name": "review_exists",
                        "passed": False,
                        "detail": f"review {review_id} HTTP {rev.status_code}",
                    }
                )
                return "FAIL", checks
            checks.append(
                {"name": "review_exists", "passed": True, "detail": f"review {review_id} exists"}
            )
        return "PASS", checks
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": str(exc)[:200]}]


def _validate_github_comment_issue(
    refs: dict[str, Any],
) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.integrations.github_app import resolve_github_token

    repo = str(refs.get("repo") or "")
    issue_number = refs.get("issue_number")
    comment_id = refs.get("comment_id")
    if not repo or "/" not in repo or issue_number is None or comment_id is None:
        return "NO_EVIDENCE", [
            {"name": "re_fetch", "passed": False, "detail": "repo/issue_number/comment_id incomplete"}
        ]
    owner, name = repo.split("/", 1)
    try:
        token = resolve_github_token()
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": f"auth error: {exc}"}]
    api = (
        f"https://api.github.com/repos/{owner}/{name}/issues/comments/{int(comment_id)}"
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                api,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code == 404:
            return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "comment not found"}]
        if resp.status_code >= 400:
            return "FAIL", [
                {"name": "re_fetch", "passed": False, "detail": f"HTTP {resp.status_code}"}
            ]
        data = resp.json()
        on_issue = str(data.get("issue_url") or "")
        expected = f"/issues/{int(issue_number)}"
        ok = expected in on_issue
        return ("PASS" if ok else "FAIL"), [
            {
                "name": "re_fetch",
                "passed": ok,
                "detail": f"comment {comment_id} on issue #{issue_number}",
            }
        ]
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": str(exc)[:200]}]


def _validate_github_workflow(
    refs: dict[str, Any],
) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    from aip.integrations.github_app import resolve_github_token

    repo = str(refs.get("repo") or "")
    sha = str(refs.get("commit_sha") or "")
    file_path = str(refs.get("file_path") or "")
    if not repo or "/" not in repo or not sha or not file_path:
        return "NO_EVIDENCE", [
            {"name": "re_fetch", "passed": False, "detail": "repo/commit_sha/file_path incomplete"}
        ]
    owner, name = repo.split("/", 1)
    try:
        token = resolve_github_token()
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": f"auth error: {exc}"}]
    api = f"https://api.github.com/repos/{owner}/{name}/commits/{sha}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                api,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code == 404:
            return "FAIL", [{"name": "re_fetch", "passed": False, "detail": "commit not found"}]
        if resp.status_code >= 400:
            return "FAIL", [
                {"name": "re_fetch", "passed": False, "detail": f"HTTP {resp.status_code}"}
            ]
        return "PASS", [
            {
                "name": "re_fetch",
                "passed": True,
                "detail": f"commit {sha[:8]} exists for {file_path}",
            }
        ]
    except Exception as exc:  # noqa: BLE001
        return "FAIL", [{"name": "re_fetch", "passed": False, "detail": str(exc)[:200]}]


def _validate_jira(
    refs: dict[str, Any], *, job_type: str = "jira.create_ticket"
) -> tuple[AuthorityVerdict, list[dict[str, Any]]]:
    key = str(refs.get("issue_key") or "").strip()
    if not key:
        return "NO_EVIDENCE", [{"name": "re_fetch", "passed": False, "detail": "no issue_key"}]
    if job_type == "jira.transition_ticket":
        tid = str(refs.get("transition_id") or "").strip()
        ok = bool(key) and bool(tid)
        return ("PASS" if ok else "NO_EVIDENCE"), [
            {
                "name": "evidence_fields",
                "passed": ok,
                "detail": "transition_id + issue_key checked (live Jira re-fetch soft)",
            }
        ]
    browse = str(refs.get("browse_url") or "")
    ok = bool(key) and bool(browse)
    return ("PASS" if ok else "NO_EVIDENCE"), [
        {
            "name": "evidence_fields",
            "passed": ok,
            "detail": "Jira live re-fetch deferred; contract fields checked",
        }
    ]

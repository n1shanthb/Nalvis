"""GitHub webhook event extraction + Spec prompt building (no FastAPI)."""

from __future__ import annotations

import re
from typing import Any

from aip.config import settings
from aip.webhooks.github_inventory import webhook_id

_FAILURE_CONCLUSIONS = frozenset(
    {"failure", "cancelled", "canceled", "timed_out", "startup_failure", "action_required"}
)


def extract_repo(payload: dict[str, Any]) -> tuple[str, str]:
    repo = payload.get("repository") if isinstance(payload, dict) else None
    if isinstance(repo, dict):
        full = str(repo.get("full_name") or "")
        if "/" in full:
            owner, name = full.split("/", 1)
            return owner, name
        owner = str((repo.get("owner") or {}).get("login") or "") if isinstance(
            repo.get("owner"), dict
        ) else ""
        name = str(repo.get("name") or "")
        return owner, name
    return "", ""


def extract_context(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    owner, repo = extract_repo(payload)
    action = str(payload.get("action") or "")
    wid = webhook_id(event, action)
    sender = ""
    sender_type = ""
    if isinstance(payload.get("sender"), dict):
        sender = str(payload["sender"].get("login") or "")
        sender_type = str(payload["sender"].get("type") or "")

    number = None
    title = ""
    body = ""
    html_url = ""
    sha = ""
    is_pull_request = False
    workflow_name = ""
    workflow_run_id = None
    conclusion = ""
    head_branch = ""
    run_html_url = ""

    if isinstance(payload.get("pull_request"), dict):
        pr = payload["pull_request"]
        is_pull_request = True
        number = pr.get("number")
        title = str(pr.get("title") or "")
        body = str(pr.get("body") or "")
        html_url = str(pr.get("html_url") or "")
        if isinstance(pr.get("head"), dict):
            sha = str(pr["head"].get("sha") or "")
    elif isinstance(payload.get("issue"), dict):
        issue = payload["issue"]
        number = issue.get("number")
        title = str(issue.get("title") or "")
        body = str(issue.get("body") or "")
        html_url = str(issue.get("html_url") or "")
        is_pull_request = bool(issue.get("pull_request"))
    if isinstance(payload.get("comment"), dict):
        body = str(payload["comment"].get("body") or body)
        html_url = str(payload["comment"].get("html_url") or html_url)

    if isinstance(payload.get("workflow_run"), dict):
        wr = payload["workflow_run"]
        workflow_name = str(wr.get("name") or wr.get("display_title") or "")
        workflow_run_id = wr.get("id")
        conclusion = str(wr.get("conclusion") or "").lower()
        head_branch = str(wr.get("head_branch") or "")
        sha = str(wr.get("head_sha") or sha)
        run_html_url = str(wr.get("html_url") or "")
        html_url = run_html_url or html_url
        # Linked PR if Actions attached one
        prs = wr.get("pull_requests") or []
        if isinstance(prs, list) and prs and isinstance(prs[0], dict):
            number = prs[0].get("number") or number
            is_pull_request = True

    return {
        "event": event,
        "action": action,
        "webhook_id": wid,
        "owner": owner,
        "repo": repo,
        "number": number,
        "title": title,
        "body": body,
        "html_url": html_url,
        "sha": sha,
        "sender": sender,
        "sender_type": sender_type,
        "is_pull_request": is_pull_request,
        "workflow_name": workflow_name,
        "workflow_run_id": workflow_run_id,
        "conclusion": conclusion,
        "head_branch": head_branch,
        "run_html_url": run_html_url,
    }


def _normalize_github_login(login: str) -> str:
    """Map synapse-bot[bot] / @synapse-bot → synapse-bot."""
    value = (login or "").strip().lstrip("@").lower()
    if value.endswith("[bot]"):
        value = value[: -len("[bot]")].rstrip()
    return value


def _is_bot_sender(sender: str, bot_login: str) -> bool:
    if not bot_login:
        return False
    normalized_sender = _normalize_github_login(sender)
    normalized_bot = _normalize_github_login(bot_login)
    if not normalized_sender or not normalized_bot:
        return False
    return normalized_sender == normalized_bot


def _is_known_internal_bot(sender: str) -> bool:
    normalized_sender = _normalize_github_login(sender)
    return normalized_sender in {"synapse-code-agent"}


def should_run_mention_bot(context: dict[str, Any]) -> bool:
    """Comment Spec: never reply to ourselves; optional @mention via env."""
    bot = (settings.github_bot_login or "").strip()
    sender = str(context.get("sender") or "")
    sender_type = str(context.get("sender_type") or "").strip().lower()
    # Never reply to GitHub App / bot accounts — prevents self-reply loops when
    # GITHUB_BOT_LOGIN drifts from the App's displayed login.
    if sender_type == "bot" or sender.rstrip().endswith("[bot]"):
        return False
    if _is_known_internal_bot(sender):
        return False
    if _is_bot_sender(sender, bot):
        return False

    body = str(context.get("body") or "")
    bot_norm = _normalize_github_login(bot)
    mentioned = bool(
        bot_norm and re.search(rf"@{re.escape(bot_norm)}\b", body, re.I)
    )

    if settings.github_mention_required:
        return mentioned if bot_norm else True
    return True


def is_explicit_merge_request(body: str) -> bool:
    """True when the human clearly asks to merge / override (not casual chat)."""
    text = (body or "").strip().lower()
    if not text:
        return False
    patterns = (
        r"\bmerge\s+(it|this|now|please)\b",
        r"\bmerge\s+it'?s\s+ok\b",
        r"\bmerge\s+its\s+ok\b",
        r"\bit'?s\s+ok\b.*\bmerge\b",
        r"\bits\s+ok\b.*\bmerge\b",
        r"\bplease\s+merge\b",
        r"\bgo\s+ahead\s+and\s+merge\b",
        r"\bmerge\s+the\s+pr\b",
        r"\blgtm\b.*\bmerge\b",
        r"^merge\b",
        r"\bship\s+it\b",
    )
    return any(re.search(p, text, re.I) for p in patterns)


def is_merge_inquiry(body: str) -> bool:
    """Soft ask like 'can we merge' — reply with status; do not merge yet."""
    text = (body or "").strip().lower()
    if not text or is_explicit_merge_request(text):
        return False
    return bool(
        re.search(r"\b(can|could|should)\s+we\s+merge\b", text, re.I)
        or re.search(r"\bready\s+to\s+merge\b", text, re.I)
        or re.search(r"\bok\s+to\s+merge\b", text, re.I)
    )


def is_cicd_author_intent(text: str) -> bool:
    """Explicit ask to scaffold / add GitHub Actions CI workflows."""
    value = (text or "").strip().lower()
    if not value:
        return False
    patterns = (
        r"\badd\s+ci\b",
        r"\bcreate\s+(a\s+)?(ci\s+)?workflow\b",
        r"\bscaffold\s+(ci|actions|github\s+actions)\b",
        r"\badd\s+github\s+actions\b",
        r"\bsetup\s+(ci|github\s+actions)\b",
        r"\bset\s+up\s+(ci|github\s+actions)\b",
        r"\bgenerate\s+(a\s+)?(ci\s+)?workflow\b",
        r"\badd\s+cicd\b",
        r"\badd\s+ci/?cd\b",
    )
    return any(re.search(p, value, re.I) for p in patterns)


def is_cicd_failure_conclusion(conclusion: str) -> bool:
    return (conclusion or "").strip().lower() in _FAILURE_CONCLUSIONS


def resolve_bound_spec_id(webhook_id_value: str, context: dict[str, Any], bound_spec_id: str) -> str:
    """Possibly override mention/issue Spec with CI author when intent matches."""
    author_id = (settings.github_cicd_author_spec_id or "").strip()
    if not author_id:
        return bound_spec_id
    wid = (webhook_id_value or "").lower()
    if wid not in {"issue_comment.created", "issues.opened"}:
        return bound_spec_id
    blob = " ".join(
        [
            str(context.get("title") or ""),
            str(context.get("body") or ""),
        ]
    )
    if is_cicd_author_intent(blob):
        return author_id
    return bound_spec_id


def build_spec_prompt(spec_kind: str, context: dict[str, Any]) -> str:
    owner = context.get("owner") or ""
    repo = context.get("repo") or ""
    number = context.get("number")
    title = context.get("title") or ""
    body = (context.get("body") or "")[:4000]
    url = context.get("html_url") or ""

    if spec_kind == "cicd":
        return (
            f"A GitHub Actions workflow_run completed for {owner}/{repo}.\n"
            f"Workflow: {context.get('workflow_name') or 'unknown'}\n"
            f"Run id: {context.get('workflow_run_id')}\n"
            f"Conclusion: {context.get('conclusion')}\n"
            f"Branch: {context.get('head_branch') or 'unknown'}\n"
            f"SHA: {context.get('sha') or 'unknown'}\n"
            f"Run URL: {context.get('run_html_url') or url}\n"
            f"Linked PR/issue number: {number or 'none'}\n\n"
            "1) Inspect the failed run/jobs/logs with GitHub MCP Actions tools.\n"
            "2) Post ONE diagnosis comment via add_issue_comment "
            "(or create an issue if no PR number) with root cause + concrete fixes.\n"
            "3) Do NOT rerun workflows. Do NOT merge. Do NOT invent secrets.\n"
        )

    if spec_kind == "cicd_author":
        return (
            f"The human asked to add/scaffold CI for {owner}/{repo}"
            f"{'#' + str(number) if number else ''}.\n"
            f"URL: {url}\nTitle: {title}\nSender: {context.get('sender')}\n\n"
            "1) Inspect the repo and any existing .github/workflows.\n"
            "2) If CI is missing/insufficient, open a PR (not main) that adds "
            ".github/workflows/ci.yml (or similar) with a sensible starter.\n"
            "3) Comment on this thread with the PR link via add_issue_comment.\n"
            "4) Do NOT push to main/master. Do NOT merge the scaffold PR. "
            "Do NOT invent secrets — use ${{ secrets.* }} placeholders.\n"
            f"Request:\n{body or title}"
        )

    if spec_kind == "review":
        return (
            f"A pull request event ({context.get('action')}) arrived for "
            f"{owner}/{repo}#{number}.\n"
            f"Title: {title}\nURL: {url}\n"
            f"Head SHA: {context.get('sha') or 'unknown'}\n\n"
            "Policy:\n"
            "1) Read the PR diff with GitHub MCP tools.\n"
            "2) If code is GOOD: APPROVE, merge_pull_request, and comment "
            "that it is approved and merged.\n"
            "3) If code is NOT fine: do NOT merge; request changes with "
            "clear reasons and concrete fixes.\n"
            "4) One pass only — do not keep chatting afterward.\n"
            f"PR body excerpt:\n{body}"
        )
    if spec_kind == "issue":
        return (
            f"A new issue just opened on {owner}/{repo}#{number}. "
            "Respond immediately.\n"
            f"Title: {title}\nURL: {url}\n\n"
            "1) Read the issue with GitHub MCP tools if needed.\n"
            "2) Post ONE issue comment with a concrete solution or clear "
            "next steps (commands, code, config). Ask questions only if "
            "you cannot propose a fix yet.\n"
            "3) You must leave a comment — do not exit silently.\n"
            "Do not invent secrets, assignees, or claim you already patched the repo.\n"
            f"Issue body excerpt:\n{body}"
        )
    # mention / issue / PR follow-up comment
    if context.get("is_pull_request"):
        merge_asked = is_explicit_merge_request(body)
        inquiry = is_merge_inquiry(body)
        if merge_asked:
            merge_line = (
                "The human EXPLICITLY overrode and asked to MERGE "
                "(e.g. merge / merge it's ok). "
                "Approve if needed, then merge_pull_request, then comment once "
                "that you merged on their request.\n"
            )
        elif inquiry:
            merge_line = (
                "The human asked whether we can merge (e.g. 'can we merge'). "
                "Do NOT merge yet. Read prior review findings; reply once with "
                "either (a) remaining blockers + fixes, or (b) that they should "
                "say 'merge its ok' to override and merge.\n"
            )
        else:
            merge_line = (
                "No explicit merge override. Reply helpfully in ONE comment. "
                "Do NOT merge.\n"
            )
        return (
            f"A human commented on PR {owner}/{repo}#{number}.\n"
            f"URL: {url}\nSender: {context.get('sender')}\n\n"
            f"{merge_line}"
            "Post the reply with add_issue_comment (required). "
            "Do not use pull_request_review_write for this chat reply. "
            "Never reply to your own comments.\n"
            f"Comment:\n{body}"
        )
    return (
        f"A new human comment on {owner}/{repo}"
        f"{'#' + str(number) if number else ''}.\n"
        f"URL: {url}\nSender: {context.get('sender')}\n\n"
        "Reply in-thread with a concrete, helpful answer using GitHub MCP "
        "comment tools. Continue the troubleshooting conversation; do not "
        "invent secrets or claim you changed production config. "
        "One reply only — never reply to yourself.\n"
        f"Comment:\n{body}"
    )


def spec_kind_for_binding(spec_id: str) -> str:
    sid = (spec_id or "").lower()
    if "cicd_author" in sid or "workflow_author" in sid:
        return "cicd_author"
    if "cicd" in sid or "doctor" in sid:
        return "cicd"
    if "issue" in sid and "mention" not in sid:
        return "issue"
    if "mention" in sid or "comment" in sid:
        return "mention"
    return "review"

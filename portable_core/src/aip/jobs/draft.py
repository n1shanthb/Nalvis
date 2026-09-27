"""Draft write payloads (review body, comments, replies) before HIL or execution."""

from __future__ import annotations

from typing import Any

_PLACEHOLDER_MARKERS = (
    "[agentsuite] pr review",
    "[agentsuite pr review]",
    "agentsuite review",
    "[agentsuite]",
)


def _is_placeholder_text(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    if len(t) < 24 and any(m in t for m in _PLACEHOLDER_MARKERS):
        return True
    return t in {"pr review", "review", "comment", "reply"}


def needs_content_draft(job_type: str, action: dict[str, Any]) -> bool:
    """True when a write job lacks substantive user-facing text."""
    action = action or {}
    if job_type == "github.review_pr":
        body = str(action.get("body") or action.get("comment") or "")
        return _is_placeholder_text(body)
    if job_type == "github.comment_issue":
        body = str(action.get("body") or action.get("comment") or "")
        return _is_placeholder_text(body)
    if job_type == "gmail.send_email":
        if str(action.get("message_id") or "").strip():
            body = str(action.get("body") or "")
            return _is_placeholder_text(body)
    if job_type == "github.create_issue":
        body = str(action.get("body") or "")
        return not body.strip()
    return False


def draft_job_action(
    job_type: str,
    action: dict[str, Any],
    *,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return action with drafted body/comment when missing. Never raises."""
    out = dict(action or {})
    signal = dict(signal or {})
    if not needs_content_draft(job_type, out):
        return out
    try:
        if job_type == "github.review_pr":
            out["body"] = draft_pr_review_body(out, signal=signal)
        elif job_type == "github.comment_issue":
            out["body"] = draft_issue_comment_body(out, signal=signal)
        elif job_type == "gmail.send_email":
            out["body"] = draft_gmail_reply_body(out, signal=signal)
        elif job_type == "github.create_issue":
            out["body"] = draft_issue_body(out, signal=signal)
    except Exception as exc:  # noqa: BLE001
        out["_draft_error"] = str(exc)[:240]
    return out


def draft_pr_review_body(action: dict[str, Any], *, signal: dict[str, Any] | None = None) -> str:
    from aip.integrations.github_app import get_pull_request_context
    from aip.jobs.execute import _github_owner_repo

    signal = dict(signal or {})
    owner, repo = _github_owner_repo(action, prefer_app_repo=True)
    pull_number = action.get("pull_number") or action.get("pr_number") or action.get("number")
    if pull_number is None:
        return _fallback_pr_review(action, signal, pr_ctx={})

    pr_ctx = get_pull_request_context(owner=owner, repo=repo, pull_number=int(pull_number))
    if pr_ctx.get("error"):
        return _fallback_pr_review(action, signal, pr_ctx=pr_ctx)

    from aip.llm.client import chat_completion_text, llm_configured

    if llm_configured():
        files = pr_ctx.get("files") or []
        file_lines = []
        for f in files[:15]:
            if not isinstance(f, dict):
                continue
            fn = f.get("filename") or "?"
            st = f.get("status") or ""
            patch = str(f.get("patch") or "").strip()
            file_lines.append(f"- `{fn}` ({st}, +{f.get('additions','0')}/-{f.get('deletions','0')})")
            if patch:
                file_lines.append(f"  ```diff\n{patch[:800]}\n  ```")
        prompt = (
            f"Repository: {owner}/{repo}\n"
            f"PR #{pull_number}: {pr_ctx.get('title') or signal.get('title') or ''}\n"
            f"Author: {pr_ctx.get('author') or ''}\n"
            f"Branch: {pr_ctx.get('head_branch')} → {pr_ctx.get('base_branch')}\n"
            f"Diff stats: +{pr_ctx.get('additions')} / -{pr_ctx.get('deletions')} "
            f"across {pr_ctx.get('changed_files')} files, {pr_ctx.get('commits')} commits\n\n"
            f"PR description:\n{(pr_ctx.get('body') or '')[:2500]}\n\n"
            f"Files changed:\n" + "\n".join(file_lines[:40]) + "\n\n"
            f"Webhook context: {signal.get('snippet') or signal.get('body_summary') or ''}\n"
        )
        text = chat_completion_text(
            system=(
                "You are a senior software engineer writing a GitHub pull request review. "
                "Output Markdown only — no JSON, no placeholders, no '[agentsuite]' tags. "
                "Structure: ## Summary, ## What changed, ## Feedback (specific, file-level "
                "when possible), ## Questions / risks, ## Suggested next steps. "
                "Be concrete and actionable; cite filenames from the diff when relevant."
            ),
            user=prompt,
            temperature=0.25,
        )
        if text and not _is_placeholder_text(text):
            return text.strip()

    return _fallback_pr_review(action, signal, pr_ctx=pr_ctx)


def _fallback_pr_review(
    action: dict[str, Any],
    signal: dict[str, Any],
    *,
    pr_ctx: dict[str, Any],
) -> str:
    title = str(pr_ctx.get("title") or action.get("title") or signal.get("title") or "Pull request")
    author = str(pr_ctx.get("author") or signal.get("sender") or "author")
    url = str(pr_ctx.get("html_url") or action.get("pr_url") or signal.get("html_url") or "")
    files = pr_ctx.get("files") or []
    file_bullets = "\n".join(
        f"- `{f.get('filename')}` ({f.get('status')})"
        for f in files[:12]
        if isinstance(f, dict) and f.get("filename")
    )
    body_excerpt = str(pr_ctx.get("body") or signal.get("body_summary") or "")[:800].strip()
    lines = [
        f"## Summary",
        f"Reviewing **{title}** by @{author}.",
        "",
        "## Change stats",
        f"- +{pr_ctx.get('additions', '?')} / -{pr_ctx.get('deletions', '?')} lines",
        f"- {pr_ctx.get('changed_files', len(files))} files · {pr_ctx.get('commits', '?')} commits",
        f"- `{pr_ctx.get('head_branch', '?')}` → `{pr_ctx.get('base_branch', '?')}`",
    ]
    if body_excerpt:
        lines.extend(["", "## PR description", body_excerpt])
    if file_bullets:
        lines.extend(["", "## Files changed", file_bullets])
    lines.extend(
        [
            "",
            "## Feedback",
            "- Please confirm unit/integration tests cover the changed paths.",
            "- Check for breaking API or config changes before merge.",
            "- Verify CI is green and deployment notes are updated if needed.",
            "",
            "## Suggested next steps",
            "- Address any failing checks or review comments.",
            "- Request re-review after updates.",
        ]
    )
    if url:
        lines.append(f"\n---\nPR: {url}")
    return "\n".join(lines)


def draft_issue_comment_body(action: dict[str, Any], *, signal: dict[str, Any] | None = None) -> str:
    from aip.integrations.github_app import get_issue_context
    from aip.jobs.execute import _github_owner_repo

    signal = dict(signal or {})
    owner, repo = _github_owner_repo(action, prefer_app_repo=True)
    issue_number = action.get("issue_number") or action.get("number")
    if issue_number is None:
        return _fallback_issue_comment(action, signal, issue_ctx={})

    issue_ctx = get_issue_context(owner=owner, repo=repo, number=int(issue_number))
    if issue_ctx.get("error"):
        return _fallback_issue_comment(action, signal, issue_ctx=issue_ctx)

    from aip.llm.client import chat_completion_text, llm_configured

    if llm_configured():
        prompt = (
            f"Issue #{issue_number} in {owner}/{repo}: {issue_ctx.get('title')}\n"
            f"State: {issue_ctx.get('state')} · Labels: {', '.join(issue_ctx.get('labels') or [])}\n"
            f"Author: {issue_ctx.get('author')}\n\n"
            f"Issue body:\n{(issue_ctx.get('body') or '')[:2000]}\n\n"
            f"Signal: {signal.get('snippet') or signal.get('body_summary') or ''}\n"
        )
        text = chat_completion_text(
            system=(
                "Write a helpful GitHub issue comment in Markdown. "
                "Acknowledge the report, summarize understanding, propose concrete next steps. "
                "No placeholders or bot tags."
            ),
            user=prompt,
            temperature=0.25,
        )
        if text and not _is_placeholder_text(text):
            return text.strip()
    return _fallback_issue_comment(action, signal, issue_ctx=issue_ctx)


def _fallback_issue_comment(
    action: dict[str, Any],
    signal: dict[str, Any],
    *,
    issue_ctx: dict[str, Any],
) -> str:
    title = str(issue_ctx.get("title") or action.get("title") or signal.get("title") or "Issue")
    num = issue_ctx.get("issue_number") or action.get("issue_number") or "?"
    return (
        f"Thanks for opening **{title}** (#{num}).\n\n"
        "**Triage summary**\n"
        "- We received this via automation and are tracking it in the current sprint.\n"
        "- Engineering will confirm repro steps and scope.\n\n"
        "**Next steps**\n"
        "1. Validate against latest `main`.\n"
        "2. Link a PR when a fix is ready.\n"
        "3. Post updates here if requirements change."
    )


def draft_gmail_reply_body(action: dict[str, Any], *, signal: dict[str, Any] | None = None) -> str:
    signal = dict(signal or {})
    from aip.llm.client import chat_completion_text, llm_configured

    inbound = str(signal.get("snippet") or signal.get("body_summary") or "").strip()
    subject = str(signal.get("subject") or action.get("subject") or "")
    from_addr = str(signal.get("from") or action.get("reply_to") or "")

    if llm_configured() and inbound:
        text = chat_completion_text(
            system=(
                "Write a professional, concise email reply body (plain text, no subject line). "
                "Acknowledge the sender's message and state sensible next steps."
            ),
            user=f"From: {from_addr}\nSubject: {subject}\n\nMessage:\n{inbound[:2000]}",
            temperature=0.3,
        )
        if text and not _is_placeholder_text(text):
            return text.strip()

    return (
        "Thank you for reaching out.\n\n"
        "We received your message and are reviewing it. "
        "A team member will follow up shortly with next steps.\n\n"
        "Best regards"
    )


def draft_issue_body(action: dict[str, Any], *, signal: dict[str, Any] | None = None) -> str:
    signal = dict(signal or {})
    title = str(action.get("title") or signal.get("title") or "Tracked item")
    ctx = str(signal.get("body_summary") or signal.get("snippet") or "").strip()
    if ctx:
        return f"**Context**\n\n{ctx[:2000]}\n\n---\n_Automation tracked: {title}_"
    return f"Automation request: {title}"

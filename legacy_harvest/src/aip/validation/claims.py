"""Extract claimed external actions from run evidence."""

from __future__ import annotations

from typing import Any

GITHUB_WRITE_TOOLS = frozenset(
    {
        "add_issue_comment",
        "create_issue",
        "issues_create",
        "create_or_update_issue",
        "issue_write",
    }
)
GMAIL_SEND_TOOLS = frozenset({"send_email", "send_email_reply"})


def _normalize_body(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


def extract_github_claim(
    evidence: dict[str, Any],
    run_meta: dict[str, Any],
) -> dict[str, Any] | None:
    context = evidence.get("context") or {}
    owner = str(context.get("owner") or run_meta.get("owner") or "").strip()
    repo = str(context.get("repo") or run_meta.get("repo") or "").strip()
    number = context.get("number") or run_meta.get("number")
    tool_events = evidence.get("tool_events") or []

    body = ""
    for event in tool_events:
        name = str(event.get("name") or "")
        if name not in GITHUB_WRITE_TOOLS:
            continue
        inp = event.get("input") or {}
        body = str(inp.get("body") or inp.get("comment") or "").strip()
        owner = str(inp.get("owner") or owner).strip()
        repo = str(inp.get("repo") or repo).strip()
        number = inp.get("issue_number") or inp.get("number") or number
        if body:
            break

    if run_meta.get("comment_fallback") or run_meta.get("comment_url"):
        body = body or str(evidence.get("output") or "").strip()
        return {
            "kind": "github_comment",
            "owner": owner,
            "repo": repo,
            "number": number,
            "body": body,
            "via_fallback": bool(run_meta.get("comment_fallback")),
            "comment_url": run_meta.get("comment_url"),
        }

    if body and owner and repo and number is not None:
        return {
            "kind": "github_comment",
            "owner": owner,
            "repo": repo,
            "number": int(number),
            "body": body,
            "via_fallback": False,
            "comment_url": None,
        }
    return None


def extract_gmail_claim(evidence: dict[str, Any]) -> dict[str, Any] | None:
    for event in evidence.get("tool_events") or []:
        name = str(event.get("name") or "")
        if name not in GMAIL_SEND_TOOLS:
            continue
        out = event.get("output") or {}
        if out.get("error"):
            continue
        inp = event.get("input") or {}
        # Prefer the *sent* message id from the tool output — never the inbound id.
        sent_id = str(out.get("message_id") or "").strip()
        replied_to = str(
            out.get("replied_to") or inp.get("message_id") or ""
        ).strip()
        body = str(inp.get("body") or "").strip()
        thread_id = str(out.get("thread_id") or "").strip()
        if sent_id or body or thread_id:
            return {
                "kind": "gmail_send",
                "tool": name,
                "message_id": sent_id,
                "replied_to": replied_to,
                "body": body,
                "thread_id": thread_id,
            }
    return None


def bodies_match(expected: str, observed: str) -> bool:
    a = _normalize_body(expected)
    b = _normalize_body(observed)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a

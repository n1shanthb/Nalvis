"""Verify GitHub comment claims against the live API."""

from __future__ import annotations

from typing import Any

from aip.integrations.github_app import list_issue_comments
from aip.validation.claims import bodies_match


def verify_github_comment(claim: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    owner = str(claim.get("owner") or "")
    repo = str(claim.get("repo") or "")
    number = claim.get("number")
    body = str(claim.get("body") or "")
    if not owner or not repo or number is None or not body:
        return (
            "INSUFFICIENT_EVIDENCE",
            "GitHub comment on issue/PR",
            "Missing owner/repo/number/body in claim",
            {},
        )
    try:
        comments = list_issue_comments(owner=owner, repo=repo, number=int(number))
    except Exception as exc:  # noqa: BLE001
        return "ERROR", body[:120], f"GitHub API error: {exc}", {}

    for comment in comments:
        observed = str(comment.get("body") or "")
        if bodies_match(body, observed):
            return (
                "PASS",
                body[:200],
                observed[:200],
                {"comment_id": comment.get("id"), "html_url": comment.get("html_url")},
            )
    return (
        "FAIL",
        body[:200],
        f"No matching comment on {owner}/{repo}#{number}",
        {"comments_checked": len(comments)},
    )

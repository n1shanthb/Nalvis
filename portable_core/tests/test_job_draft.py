"""Tests for write-content drafting."""

from aip.jobs.draft import (
    _fallback_pr_review,
    draft_job_action,
    needs_content_draft,
)


def test_needs_draft_when_review_body_missing() -> None:
    assert needs_content_draft("github.review_pr", {"pull_number": 1})
    assert not needs_content_draft(
        "github.review_pr",
        {"pull_number": 1, "body": "## Summary\nDetailed review with file notes."},
    )
    assert needs_content_draft("github.review_pr", {"pull_number": 1, "body": "[agentsuite] PR review"})


def test_fallback_pr_review_is_substantive() -> None:
    text = _fallback_pr_review(
        {"pull_number": 42, "title": "Add auth middleware"},
        {"sender": "dev1"},
        pr_ctx={
            "title": "Add auth middleware",
            "author": "dev1",
            "additions": 120,
            "deletions": 15,
            "changed_files": 4,
            "commits": 2,
            "head_branch": "feature/auth",
            "base_branch": "main",
            "html_url": "https://github.com/acme/app/pull/42",
            "files": [{"filename": "src/auth.py", "status": "modified"}],
        },
    )
    assert "[agentsuite]" not in text.lower()
    assert "## Summary" in text
    assert "auth middleware" in text
    assert "src/auth.py" in text


def test_draft_job_action_skips_when_body_present() -> None:
    action = {"body": "Already written review with enough detail for humans."}
    out = draft_job_action("github.review_pr", action, signal={})
    assert out["body"] == action["body"]

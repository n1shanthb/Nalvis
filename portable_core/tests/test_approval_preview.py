"""Tests for HIL approval preview builder."""

from aip.approvals.preview import build_approval_preview


def test_gmail_reply_preview_includes_inbound_trigger() -> None:
    preview = build_approval_preview(
        job_type="gmail.send_email",
        requested_action={
            "message_id": "abc123",
            "thread_id": "abc123",
            "reply_to": "user@example.com",
            "subject": "Re: Help",
        },
        job_title="Reply to user@example.com",
        policy_reason="workspace policy requires HIL for gmail.send_email",
        run_signal={
            "channel": "gmail",
            "from": "User <user@example.com>",
            "subject": "Help with billing",
            "snippet": "Please fix invoice line 3",
        },
        agent_name="Nexus Pay Gmail Comms",
    )
    ctx = preview["context"]
    assert ctx["system"] == "gmail"
    assert ctx["trigger"]["channel"] == "gmail"
    assert any(f["label"] == "To" and "user@example.com" in f["value"] for f in ctx["fields"])
    assert ctx["editableKey"] == "body"
    assert "Thank you" in ctx["editableDefault"]


def test_github_pr_review_preview_has_link() -> None:
    preview = build_approval_preview(
        job_type="github.review_pr",
        requested_action={
            "owner": "acme",
            "repo": "app",
            "pull_number": 42,
            "body": "LGTM with nits",
            "event": "COMMENT",
        },
        job_title="Review PR #42",
        policy_reason="HIL for PR writes",
        run_signal={"channel": "github", "repo": "acme/app", "pull_number": 42},
    )
    ctx = preview["context"]
    assert any(l["href"].endswith("/pull/42") for l in ctx["links"])
    assert ctx["editableDefault"] == "LGTM with nits"

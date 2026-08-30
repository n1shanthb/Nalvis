"""Agents SDK runtime wrap — no live writes."""

from __future__ import annotations

from aip.runtime.agents_sdk import execute_job_via_agents_runtime


def test_execute_via_runtime_uses_connector(monkeypatch) -> None:
    called = {}

    def fake_execute(job_type, action):
        called["job_type"] = job_type
        called["action"] = action
        return {
            "ok": True,
            "evidence": {
                "job_type": job_type,
                "refs": {"issue_url": "https://x", "repo": "a/b", "issue_number": 1},
            },
        }

    monkeypatch.setattr("aip.runtime.agents_sdk.execute_job_type", fake_execute)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = execute_job_via_agents_runtime(
        "github.create_issue",
        {"title": "t"},
        agent_role="GitHubIssueManagerAgent",
    )
    assert result["ok"] is True
    assert called["job_type"] == "github.create_issue"
    assert result.get("_via") in (
        "openai_agents_sdk_tools_direct",
        "connector_direct_sdk_unavailable",
    )

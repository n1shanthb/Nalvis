"""API unit tests (no live credentials required)."""

from __future__ import annotations

import hmac
import hashlib

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "connectors" in body


def test_tunnel_status() -> None:
    resp = client.get("/api/tunnel")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_github_webhook_accepts_unsigned_when_secret_empty(monkeypatch) -> None:
    from aip.config import settings

    monkeypatch.setattr(settings, "github_webhook_secret", "")
    payload = b'{"action":"opened","repository":{"full_name":"acme/app"}}'
    resp = client.post(
        "/api/webhooks/github",
        content=payload,
        headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["delivery"]["webhook_id"] == "issues.opened"


def test_github_webhook_rejects_bad_signature(monkeypatch) -> None:
    from aip.config import settings

    monkeypatch.setattr(settings, "github_webhook_secret", "s3cret")
    payload = b'{"action":"opened"}'
    resp = client.post(
        "/api/webhooks/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_github_webhook_accepts_valid_signature(monkeypatch) -> None:
    from aip.config import settings

    secret = "s3cret"
    monkeypatch.setattr(settings, "github_webhook_secret", secret)
    payload = b'{"action":"opened","repository":{"full_name":"acme/app"}}'
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    resp = client.post(
        "/api/webhooks/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": f"sha256={digest}",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200


def test_gmail_webhook() -> None:
    import base64
    import json

    data = base64.b64encode(json.dumps({"historyId": "123", "emailAddress": "a@b.com"}).encode()).decode()
    resp = client.post("/api/webhooks/gmail", json={"message": {"data": data, "messageId": "m1"}})
    assert resp.status_code == 200
    assert resp.json()["delivery"]["payload_summary"]["history_id"] == "123"


def test_jira_webhook(monkeypatch) -> None:
    from aip.config import settings

    monkeypatch.setattr(settings, "jira_webhook_secret", "")
    resp = client.post(
        "/api/webhooks/jira",
        json={"webhookEvent": "jira:issue_created", "issue": {"key": "ENG-1"}},
    )
    assert resp.status_code == 200
    assert resp.json()["delivery"]["payload_summary"]["issue_key"] == "ENG-1"


def test_connectors_smoke_dry_run() -> None:
    resp = client.post("/api/connectors/smoke", json={"dry_run": True})
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True


def test_integrations_health() -> None:
    resp = client.get("/api/integrations/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "integrations" in body
    assert "checked_at" in body
    names = {row["name"] for row in body["integrations"]}
    assert names == {"github", "jira", "gmail", "calendar"}
    for row in body["integrations"]:
        assert row["status"] in {"healthy", "degraded", "down", "unknown"}
        assert "credentialsConfigured" in row
        assert isinstance(row.get("config"), dict)
        assert "displayName" in row

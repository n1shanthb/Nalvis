"""Control-plane persistence + ingest tests (uses live local Postgres when available)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aip.db.schema import init_db
from aip.db.session import reset_engine, session_scope
from aip.evidence.contracts import evidence_complete, has_evidence_contract
from aip.kg.inventory import build_inventory_from_kg
from aip.kg.auditor import audit_agent_proposals
from aip.kg.synthesizer import propose_agents_from_inventory
from aip.director.router import route
from aip.director.auditor import audit_routing
from apps.api.main import app


client = TestClient(app)


SAMPLE_KG = {
    "company": "Acme",
    "products": [
        {
            "name": "Analytics",
            "repos": ["n1shanthb/analytics-resume"],
            "jira": ["ENG"],
            "calendars": ["primary"],
            "email_groups": ["user@example.com"],
            "systems": ["slack", "github", "gmail"],
        }
    ],
    "systems": ["notion", "aws"],
    "stakeholders": ["ops@acme.com"],
}


def test_evidence_contracts_authority() -> None:
    assert has_evidence_contract("github.create_issue")
    assert evidence_complete(
        "github.create_issue",
        {"issue_url": "https://x", "repo": "a/b", "issue_number": 1},
    )
    assert not evidence_complete("gmail.send_email", {"message_id": "m"})


def test_inventory_and_unsupported_proposals() -> None:
    inv = build_inventory_from_kg(json.dumps(SAMPLE_KG))
    assert "Analytics" in inv.products
    assert any(r.kind == "system" and r.name == "slack" for r in inv.resources)
    proposals = propose_agents_from_inventory(inv)
    audit = audit_agent_proposals(inv, proposals)
    roles = {p.role for p in audit.accepted}
    systems = {p.system_key for p in audit.accepted if p.status == "unsupported"}
    assert "slack" in systems or any(p.system_key == "slack" for p in audit.accepted)
    assert "notion" in systems or any(p.system_key == "notion" for p in audit.accepted)
    # No fake executors for unsupported
    for p in audit.accepted:
        if p.status == "unsupported":
            assert p.tool_scope == []


def test_director_refuses_example_invention() -> None:
    decision = route(
        agents=[
            {
                "id": "a1",
                "role": "GitHubIssueManagerAgent",
                "status": "idle",
                "activation": "ready",
                "systemKey": "github",
                "toolScope": ["github.create_issue", "github.read"],
            }
        ],
        workspace={"id": "ws", "scope": {"repos": ["n1shanthb/analytics-resume"]}},
        objectives=["customer is upset about billing"],
        plan=None,
        signal={},
    )
    assert decision.jobs == []
    assert any("refusing" in n.lower() or "no structured" in n.lower() for n in decision.notes)


def test_director_structured_plan_routes() -> None:
    agents = [
        {
            "id": "a1",
            "role": "GitHubIssueManagerAgent",
            "status": "idle",
            "activation": "ready",
            "systemKey": "github",
            "toolScope": ["github.create_issue", "github.read"],
        }
    ]
    workspace = {
        "id": "ws",
        "scope": {"repos": ["n1shanthb/analytics-resume"], "jiraKeys": [], "calendars": [], "emailGroups": []},
    }
    decision = route(
        agents=agents,
        workspace=workspace,
        objectives=["track work"],
        plan=[{"job_type": "github.create_issue", "agent_role": "GitHubIssueManagerAgent", "requested_action": {"title": "t"}}],
    )
    audited = audit_routing(decision, agents=agents, workspace=workspace)
    assert len(audited.accepted) == 1
    assert audited.accepted[0].requested_action.get("owner") == "n1shanthb"


@pytest.fixture(scope="module")
def db_ready() -> bool:
    try:
        reset_engine()
        init_db()
        with session_scope() as session:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not available: {exc}")
        return False


def test_control_plane_empty_state(db_ready: bool) -> None:
    assert db_ready
    resp = client.get("/api/demo/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "workspaces" in body
    assert "runs" in body
    assert "agents" in body
    # Anti-fake-data: may be empty lists, never invented demo tenants
    assert isinstance(body["runs"], list)
    assert isinstance(body["agents"], list)


def test_ingest_creates_workspaces_and_unsupported(db_ready: bool) -> None:
    assert db_ready
    client.delete("/api/demo/state")
    resp = client.post(
        "/api/context/ingest",
        json={"raw": json.dumps(SAMPLE_KG), "source": "paste"},
    )
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["parsePreview"]["workspacesDerived"] >= 1

    agents = client.get("/api/agents").json()
    assert isinstance(agents, list)
    unsupported = [a for a in agents if a.get("status") == "unsupported"]
    assert any(a.get("systemKey") in ("slack", "notion", "aws") for a in unsupported)

    workspaces = client.get("/api/workspaces").json()
    assert any(w["name"] == "Analytics" for w in workspaces)


def test_clear_all_ops_data(db_ready: bool) -> None:
    assert db_ready
    client.post(
        "/api/context/ingest",
        json={"raw": json.dumps(SAMPLE_KG), "source": "paste"},
    )
    assert client.get("/api/workspaces").json()
    cleared = client.delete("/api/demo/state")
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["workspaces"] == []
    assert body["agents"] == []
    assert body["runs"] == []
    assert body["validations"] == []
    assert body["contextDocuments"] == []
    assert body.get("companyName", "") == ""


def test_list_endpoints(db_ready: bool) -> None:
    assert db_ready
    for path in (
        "/api/workspaces",
        "/api/runs",
        "/api/jobs",
        "/api/approvals",
        "/api/policies",
        "/api/validations",
        "/api/agents",
        "/api/integrations/health",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path

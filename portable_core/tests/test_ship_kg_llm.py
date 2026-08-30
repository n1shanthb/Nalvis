"""Ship-goal unit tests: LLM client, graph KG inventory, recommendation floor."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
EX2 = ROOT.parent / "ex2.json" if not (ROOT / "ex2.json").exists() else ROOT / "ex2.json"
# portable_core/tests → parents[1]=portable_core, parents[2]=agentsuite
REPO = Path(__file__).resolve().parents[2]
EX2_PATH = REPO / "ex2.json"


def test_resolve_llm_prefers_openai_then_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    from aip.llm.client import reset_llm_client_cache, resolve_llm_api_key, resolve_llm_base_url

    reset_llm_client_cache()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    assert resolve_llm_api_key() == "sk-or-test"
    assert resolve_llm_base_url() == "https://openrouter.ai/api/v1"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_API_BASE", "https://example.com/v1")
    assert resolve_llm_api_key() == "sk-openai"
    assert resolve_llm_base_url() == "https://example.com/v1"
    reset_llm_client_cache()


def test_director_llm_route_with_openrouter_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from aip.director.router import route
    from aip.llm.client import reset_llm_client_cache

    reset_llm_client_cache()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("LLM_API_BASE", "https://openrouter.ai/api/v1")

    agents = [
        {
            "id": "agt-gh",
            "role": "GitHubIssueManagerAgent",
            "status": "idle",
            "activation": "ready",
            "systemKey": "github",
            "toolScope": ["github.create_issue", "github.read"],
        },
        {
            "id": "agt-cal",
            "role": "CalendarSchedulerAgent",
            "status": "idle",
            "activation": "ready",
            "systemKey": "calendar",
            "toolScope": ["calendar.create_event", "calendar.update_event"],
        },
    ]
    workspace = {
        "id": "ws-x",
        "scope": {"repos": ["acme/app"], "calendars": ["primary"]},
    }

    fake = {
        "jobs": [
            {
                "agent_id": "agt-gh",
                "job_type": "github.create_issue",
                "requested_action": {"title": "from free text"},
                "confidence": 0.8,
                "rationale": "objective mentions github work",
            }
        ]
    }
    with patch("aip.llm.client.chat_completion_json", return_value=fake):
        decision = route(
            agents=agents,
            workspace=workspace,
            objectives=["Please open a GitHub issue about the login bug"],
            plan=None,
            signal=None,
        )
    assert decision.jobs, decision.notes
    assert decision.jobs[0].job_type == "github.create_issue"
    assert decision.jobs[0].agent_id == "agt-gh"
    reset_llm_client_cache()


def _truncated_ex2() -> dict:
    raw = json.loads(EX2_PATH.read_text(encoding="utf-8"))
    nodes = list(raw.get("nodes") or [])
    # Keep repos + attention mail + a couple files
    keep_ids: set[str] = set()
    kept_nodes = []
    for n in nodes:
        et = (n.get("type") or "").lower()
        attn = n.get("attention") or {}
        if et == "repository" or attn.get("recommended_agent") or n.get("need_attention"):
            kept_nodes.append(n)
            keep_ids.add(str(n.get("id")))
        elif et == "email" and len([x for x in kept_nodes if (x.get("type") or "") == "email"]) < 2:
            kept_nodes.append(n)
            keep_ids.add(str(n.get("id")))
    # pad with one file if present
    for n in nodes:
        if (n.get("type") or "").lower() == "file" and len(kept_nodes) < 8:
            kept_nodes.append(n)
            keep_ids.add(str(n.get("id")))
            break
    links = [
        e
        for e in (raw.get("links") or raw.get("edges") or [])
        if str(e.get("source")) in keep_ids or str(e.get("target")) in keep_ids
    ]
    return {"nodes": kept_nodes, "links": links, "company": "synapse-test"}


def test_graph_inventory_from_ex2_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aip.kg.inventory.probe_connector_availability",
        lambda: __import__("aip.kg.inventory", fromlist=["ConnectorAvailability"]).ConnectorAvailability(
            available={"github", "gmail", "calendar"},
            details={},
        ),
    )
    from aip.kg.inventory import build_inventory_from_kg, parse_preview_from_inventory

    fixture = _truncated_ex2()
    inv = build_inventory_from_kg(json.dumps(fixture))
    preview = parse_preview_from_inventory(inv)
    assert preview["format"] == "graph"
    assert any(r.kind == "repo" for r in inv.resources)
    assert "github" in preview["systems"]
    assert "gmail" in preview["systems"]
    assert preview["attentionNodes"], "expected recommended_agent / need_attention node"


def test_flat_ex1_style_entity_graph_extracts_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    """ex1.json uses type=Entity + source_type=github — must still find owner/repo slugs."""
    monkeypatch.setattr(
        "aip.kg.inventory.probe_connector_availability",
        lambda: __import__("aip.kg.inventory", fromlist=["ConnectorAvailability"]).ConnectorAvailability(
            available={"github", "gmail", "calendar"},
            details={},
        ),
    )
    from aip.kg.inventory import build_inventory_from_kg, parse_preview_from_inventory
    from aip.kg.synthesizer import propose_agents_from_inventory
    from aip.kg.auditor import audit_agent_proposals

    raw = {
        "nodes": [
            {
                "id": "1",
                "name": "Terminal-agent",
                "type": "Entity",
                "group_id": "synapse",
                "source_type": "github",
                "summary": "Clone from github.com/Santhoshkumar044/Terminal-agent.git",
            },
            {
                "id": "2",
                "name": "daemon",
                "type": "Entity",
                "group_id": "synapse",
                "source_type": "github",
                "summary": "GitHub Repository navdeep-r/daemon",
            },
            {
                "id": "3",
                "name": "noise",
                "type": "Entity",
                "source_type": "github",
                "summary": "Signup/login flow and Workspace/task hierarchy — not a repo",
            },
        ],
        "edges": [],
    }
    inv = build_inventory_from_kg(json.dumps(raw))
    repos = sorted({r.name for r in inv.resources if r.kind == "repo"})
    assert repos == ["Santhoshkumar044/Terminal-agent", "navdeep-r/daemon"]
    assert "Terminal-agent" in inv.products or "daemon" in inv.products
    assert "Signup/login" not in repos
    preview = parse_preview_from_inventory(inv)
    assert "github" in preview["systems"]
    props = propose_agents_from_inventory(inv)
    aud = audit_agent_proposals(inv, props)
    assert any(p.role == "GitHubIssueManagerAgent" and p.status == "idle" for p in aud.accepted)
    monkeypatch.setattr(
        "aip.kg.inventory.probe_connector_availability",
        lambda: __import__("aip.kg.inventory", fromlist=["ConnectorAvailability"]).ConnectorAvailability(
            available={"github"},
            details={},
        ),
    )
    from aip.kg.inventory import build_inventory_from_kg

    raw = {
        "company": "FlatCo",
        "products": [{"name": "P1", "repos": ["acme/app"], "systems": ["slack"]}],
    }
    inv = build_inventory_from_kg(json.dumps(raw))
    assert inv.products == ["P1"]
    assert any(r.kind == "repo" and r.name == "acme/app" for r in inv.resources)
    assert any(r.kind == "system" and r.name == "slack" for r in inv.resources)


def test_recommended_agent_floor_plus_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    from aip.kg.inventory import CompanyInventory, ConnectorAvailability, InventoryResource
    from aip.kg.synthesizer import propose_agents_from_inventory

    monkeypatch.setattr("aip.kg.synthesizer.llm_configured", lambda: False)
    inv = CompanyInventory(
        company_name="synapse",
        products=["synapse"],
        availability=ConnectorAvailability(available={"github", "gmail"}, details={}),
        resources=[
            InventoryResource(kind="product", name="synapse", owner_product="synapse", evidence_path="$.p"),
            InventoryResource(
                kind="repo",
                name="navdeep-r/CHAT-SYSTEM",
                owner_product="synapse",
                evidence_path="$.nodes[id=repo-1]",
            ),
            InventoryResource(
                kind="system",
                name="github",
                owner_product="synapse",
                evidence_path="$.inferred",
            ),
            InventoryResource(
                kind="email",
                name="Email: sorry",
                owner_product="synapse",
                evidence_path="$.nodes[id=mail-1]",
                attrs={
                    "need_attention": True,
                    "source_type": "mail",
                    "attention": {"recommended_agent": "Developer", "required": True},
                },
            ),
            InventoryResource(
                kind="email_group",
                name="navdeep@example.com",
                owner_product="synapse",
                evidence_path="$.nodes[id=mail-1].email",
            ),
            InventoryResource(
                kind="system",
                name="gmail",
                owner_product="synapse",
                evidence_path="$.inferred.mail",
            ),
            InventoryResource(
                kind="system",
                name="slack",
                owner_product="synapse",
                evidence_path="$.text:slack",
            ),
        ],
        raw={"nodes": []},
    )
    proposals = propose_agents_from_inventory(inv)
    roles = {p.role for p in proposals}
    # Floor: Developer hint → GitHub specializations
    assert "GitHubIssueManagerAgent" in roles
    # Ceiling: discovery still adds Gmail + more GitHub + unsupported slack
    assert "GmailCommsAgent" in roles or "GitHubPRReviewerAgent" in roles
    assert any(p.system_key == "slack" and p.status == "unsupported" for p in proposals)
    # Origin path to attention node on at least one github floor agent
    floor = [
        p
        for p in proposals
        if "recommended_agent:Developer" in p.origin_signals
    ]
    assert floor, "recommendation floor must emit origin signals"
    assert any("mail-1" in path or "mail" in path for p in floor for path in p.origin_paths)


EX3_PATH = REPO / "ex3.json"


def test_ex3_graph_products_exclude_company_and_repo_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """ex3: company is not a product; repo slugs are not duplicated as products."""
    if not EX3_PATH.exists():
        pytest.skip("ex3.json fixture missing")
    monkeypatch.setattr(
        "aip.kg.inventory.probe_connector_availability",
        lambda: __import__("aip.kg.inventory", fromlist=["ConnectorAvailability"]).ConnectorAvailability(
            available={"github", "gmail", "calendar"},
            details={},
        ),
    )
    from aip.kg.inventory import build_inventory_from_kg, parse_preview_from_inventory

    inv = build_inventory_from_kg(EX3_PATH.read_text(encoding="utf-8"))
    preview = parse_preview_from_inventory(inv)
    assert inv.company_name == "HelioStack Inc"
    assert preview["products"] == ["Resume Analytics", "Ops Console"]
    assert set(preview["repos"]) == {"n1shanthb/analytics-resume", "heliostack/ops-console"}
    assert preview["workspacesDerived"] == 2

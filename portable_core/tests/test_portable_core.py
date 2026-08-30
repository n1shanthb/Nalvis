"""Contract tests for portable_core (Phase 0A)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_authority_verdict_mapping() -> None:
    from aip.validation.verdicts import to_authority_verdict

    assert to_authority_verdict("PASS") == "PASS"
    assert to_authority_verdict("FAIL") == "FAIL"
    assert to_authority_verdict("INSUFFICIENT_EVIDENCE") == "NO_EVIDENCE"
    assert to_authority_verdict("ERROR") == "FAIL"
    assert to_authority_verdict("PARTIAL") == "FAIL"
    assert to_authority_verdict("REVIEW") == "NO_EVIDENCE"
    assert to_authority_verdict("") == "NO_EVIDENCE"
    assert to_authority_verdict(None) == "NO_EVIDENCE"


def test_evidence_roundtrip() -> None:
    from aip.validation.evidence import clear_evidence, get_evidence, save_run_evidence

    clear_evidence()
    save_run_evidence(
        "exec-1",
        spec_id="agent-a",
        project_id="proj-1",
        system="github",
        objective="comment",
        success=True,
        output="done",
        error=None,
        tool_events=[{"name": "add_issue_comment", "input": {"body": "hi"}}],
        context={"owner": "acme", "repo": "app", "number": 1},
        run_meta={"owner": "acme"},
    )
    ev = get_evidence("exec-1")
    assert ev["spec_id"] == "agent-a"
    assert ev["tool_events"][0]["name"] == "add_issue_comment"
    assert get_evidence("missing") == {}


def test_github_claim_extraction() -> None:
    from aip.validation.claims import extract_github_claim

    evidence = {
        "tool_events": [
            {
                "name": "add_issue_comment",
                "input": {
                    "owner": "acme",
                    "repo": "app",
                    "issue_number": 7,
                    "body": "LGTM",
                },
            }
        ],
        "context": {},
    }
    claim = extract_github_claim(evidence, {})
    assert claim is not None
    assert claim["owner"] == "acme"
    assert claim["number"] == 7
    assert claim["body"] == "LGTM"


def test_gmail_claim_missing_is_none() -> None:
    from aip.validation.claims import extract_gmail_claim

    assert extract_gmail_claim({"tool_events": []}) is None


def test_validate_after_run_no_evidence_maps_to_authority() -> None:
    from aip.validation.engine import validate_after_run
    from aip.validation.evidence import clear_evidence

    clear_evidence()
    record = validate_after_run(
        execution_id="e2",
        spec_id="spec",
        project_id="p1",
        system="github",
        success=True,
        output="I reviewed the PR",
        error=None,
        tool_events=[],
        context={},
        run_meta={},
    )
    assert record.verdict == "INSUFFICIENT_EVIDENCE"
    assert record.authority_verdict == "NO_EVIDENCE"
    assert record.evidence_refs["authority_verdict"] == "NO_EVIDENCE"


def test_guardrail_engine_deny_precedence() -> None:
    from aip.guardrails.decisions import PolicyRequest
    from aip.guardrails.engine import GuardrailEngine
    from aip.guardrails.identity import AgentExecutionIdentity
    from aip.guardrails.models import Guardrail, GuardrailEffect

    rules = [
        Guardrail(id="allow-1", action="send_email", effect=GuardrailEffect.ALLOW),
        Guardrail(id="deny-1", action="send_email", effect=GuardrailEffect.DENY),
    ]
    engine = GuardrailEngine(rules)
    decision = engine.evaluate(
        PolicyRequest(
            identity=AgentExecutionIdentity(
                agent_id="a1",
                execution_id="e1",
                project_id="p1",
                organization_id="o1",
                environment="dev",
            ),
            tool="send_email",
            arguments={"to": "x@y.com"},
        )
    )
    assert decision.decision == GuardrailEffect.DENY
    assert decision.guardrail_id == "deny-1"


def test_guardrail_require_approval() -> None:
    from aip.guardrails.decisions import PolicyRequest
    from aip.guardrails.engine import GuardrailEngine
    from aip.guardrails.identity import AgentExecutionIdentity
    from aip.guardrails.models import Guardrail, GuardrailEffect

    engine = GuardrailEngine(
        [Guardrail(id="hil", action="merge_pull_request", effect=GuardrailEffect.REQUIRE_APPROVAL)]
    )
    decision = engine.evaluate(
        PolicyRequest(
            identity=AgentExecutionIdentity(
                agent_id="a1",
                execution_id="e1",
                project_id="p1",
                organization_id="o1",
                environment="dev",
            ),
            tool="merge_pull_request",
            arguments={},
        )
    )
    assert decision.decision == GuardrailEffect.REQUIRE_APPROVAL


def test_webhook_catalog_seeds_and_bindings() -> None:
    from aip.webhooks.catalog import WebhookCatalog
    from aip.webhooks.models import WebhookBinding

    cat = WebhookCatalog()
    cat.clear()
    webs = cat.list_webhooks()
    assert len(webs) > 10
    github = cat.list_webhooks("github")
    assert all(w.connected_system_id == "github" for w in github)
    binding = WebhookBinding(
        webhook_id="pull_request.opened",
        connected_system_id="github",
        spec_id="spec-1",
    )
    cat.upsert_binding(binding)
    assert cat.list_bindings("spec-1")[0].webhook_id == "pull_request.opened"


def test_sync_spec_bindings() -> None:
    from aip.contracts.specification import AgentSpecification
    from aip.webhooks.bind import sync_spec_bindings
    from aip.webhooks.catalog import WebhookCatalog

    cat = WebhookCatalog()
    cat.clear()
    spec = AgentSpecification.model_validate(
        {
            "agent": {"id": "pr-bot", "title": "PR Bot", "org_id": "acme"},
            "goal": "review PRs",
            "prompt": {"system": "review"},
            "trigger": {"type": "webhook", "webhook_ids": ["pull_request.opened"]},
            "metadata": {"company_id": "co1", "project_id": "gpay"},
        }
    )
    bindings = sync_spec_bindings(spec, catalog=cat)
    assert len(bindings) == 1
    assert bindings[0].spec_id == "pr-bot"
    assert bindings[0].connected_system_id == "github"


def test_builtin_presets() -> None:
    from aip.connected_systems.presets import BUILTIN_PRESETS, MVP_SYSTEM_IDS, preset_by_id

    assert MVP_SYSTEM_IDS == {"github", "jira", "gmail", "calendar"}
    assert preset_by_id("github")["transport"] == "mcp"
    assert preset_by_id("gmail")["transport"] == "native"
    assert len(BUILTIN_PRESETS) == 4


def test_agent_specification_roundtrip() -> None:
    from aip.contracts.specification import AgentSpecification

    spec = AgentSpecification.model_validate(
        {
            "agent": {"id": "x", "title": "X", "org_id": "o"},
            "goal": "do work",
            "prompt": {"system": "you are helpful"},
            "tools": ["list_events"],
        }
    )
    data = spec.model_dump()
    again = AgentSpecification.model_validate(data)
    assert again.spec_id == "x"
    assert again.tools == ["list_events"]


def test_no_forbidden_imports_in_portable_core() -> None:
    """Static scan: portable_core must not import legacy orchestration/DB wiring."""
    import ast

    root = Path(__file__).resolve().parents[1] / "src" / "aip"
    forbidden = ("aip.main", "aip.app_context", "aip.inbound", "aip.persistence")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for pref in forbidden:
                    if name == pref or name.startswith(pref + "."):
                        offenders.append(f"{path.relative_to(root)} -> {name}")
    assert offenders == [], offenders

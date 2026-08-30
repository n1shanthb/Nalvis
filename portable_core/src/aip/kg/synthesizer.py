"""Agent specialization catalog + synthesis proposals (meaning layer).

Catalog entries are Authority specializations — not scenario if-trees.
Without an LLM key, proposals are inventory-grounded catalog instantiations
(system present + scopes exist → specialization templates for that system).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aip.evidence.contracts import EXECUTABLE_SYSTEMS
from aip.kg.inventory import CompanyInventory, InventoryResource
from aip.llm.client import llm_configured


@dataclass
class AgentProposal:
    name: str
    role: str
    system_key: str
    mission: str
    tool_scope: list[str]
    workspace_product: str | None
    status: str  # idle | unsupported
    activation: str  # ready | blocked_missing_connector
    origin_paths: list[str] = field(default_factory=list)
    origin_signals: list[str] = field(default_factory=list)
    rationale: str = ""
    job_types: list[str] = field(default_factory=list)
    default_guardrails: list[dict[str, str]] = field(default_factory=list)


# Authority agent types — keyed by system family (general catalog, not examples)
SPECIALIZATION_CATALOG: list[dict[str, Any]] = [
    {
        "role": "GitHubIssueManagerAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub Issue Manager",
        "mission": "Create/triage/label/assign issues within workspace repo scope.",
        "tool_scope": ["github.create_issue", "github.comment_issue", "github.read"],
        "job_types": ["github.create_issue", "github.comment_issue"],
        "guardrails": [
            {"tool": "github.create_issue", "mode": "allow", "label": "Create issues in scope"},
            {"tool": "github.comment_issue", "mode": "hil", "label": "Comment on issues"},
        ],
    },
    {
        "role": "GitHubPRReviewerAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub PR Reviewer",
        "mission": "Add review comments and summarize checks within repo scope.",
        "tool_scope": ["github.review_pr", "github.read"],
        "job_types": ["github.review_pr"],
        "guardrails": [
            {"tool": "github.review_pr", "mode": "hil", "label": "PR review writes"},
        ],
    },
    {
        "role": "GitHubCICDAgent",
        "system": "github",
        "requires_resource": "repo",
        "name_template": "{product} GitHub CI/CD",
        "mission": "Propose or create CI workflow changes (typically HIL-gated).",
        "tool_scope": ["github.create_or_update_workflow", "github.read"],
        "job_types": ["github.create_or_update_workflow"],
        "guardrails": [
            {"tool": "github.create_or_update_workflow", "mode": "hil", "label": "CI workflow writes"},
        ],
    },
    {
        "role": "JiraSyncAgent",
        "system": "jira",
        "requires_resource": "jira_project",
        "name_template": "{product} Jira Sync",
        "mission": "Create/link/transition tickets within Jira project scope.",
        "tool_scope": ["jira.create_ticket", "jira.transition_ticket", "jira.read"],
        "job_types": ["jira.create_ticket", "jira.transition_ticket"],
        "guardrails": [
            {"tool": "jira.create_ticket", "mode": "allow", "label": "Create tickets in scope"},
            {"tool": "jira.transition_ticket", "mode": "hil", "label": "Transitions"},
        ],
    },
    {
        "role": "GmailCommsAgent",
        "system": "gmail",
        "requires_resource": "email_group",
        "name_template": "{product} Gmail Comms",
        "mission": "Draft/send emails and triage threads within comms scope.",
        "tool_scope": ["gmail.send_email", "gmail.read"],
        "job_types": ["gmail.send_email"],
        "guardrails": [
            {"tool": "gmail.send_email", "mode": "hil", "label": "External send"},
        ],
    },
    {
        "role": "CalendarSchedulerAgent",
        "system": "calendar",
        "requires_resource": "calendar",
        "name_template": "{product} Calendar Scheduler",
        "mission": "Schedule/reschedule meetings within calendar scope.",
        "tool_scope": ["calendar.create_event", "calendar.update_event", "calendar.read"],
        "job_types": ["calendar.create_event", "calendar.update_event"],
        "guardrails": [
            {"tool": "calendar.create_event", "mode": "allow", "label": "Create events"},
            {"tool": "calendar.update_event", "mode": "hil", "label": "Reschedule"},
        ],
    },
]


def _products(inv: CompanyInventory) -> list[str]:
    return list(inv.products) or ["default"]


def _has_resource(inv: CompanyInventory, product: str, kind: str) -> bool:
    kinds = {kind}
    if kind == "email_group":
        kinds.add("email")
    for r in inv.resources:
        if r.kind not in kinds:
            continue
        if r.owner_product is None or r.owner_product == product:
            return True
    return False


def _system_mentioned(inv: CompanyInventory, system: str) -> list[InventoryResource]:
    return [r for r in inv.resources if r.kind == "system" and r.name == system]


# Hint tokens → catalog roles (general mapping — never if recommended_agent=="X" trees)
_HINT_ROLE_TOKENS: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("developer", "engineer", "coder", "github", "repo", "pr", "pull", "ci", "cicd", "devops"),
        ["GitHubIssueManagerAgent", "GitHubPRReviewerAgent", "GitHubCICDAgent"],
    ),
    (("jira", "ticket", "issue tracker", "atlassian"), ["JiraSyncAgent"]),
    (("gmail", "email", "mail", "comms", "communication"), ["GmailCommsAgent"]),
    (("calendar", "schedule", "meeting", "scheduler"), ["CalendarSchedulerAgent"]),
]


def map_recommended_hint_to_roles(hint: str) -> list[str]:
    """Map a free-text recommended_agent hint to Authority catalog roles (floor)."""
    h = (hint or "").strip().lower()
    if not h:
        return []
    matched: list[str] = []
    for tokens, roles in _HINT_ROLE_TOKENS:
        if any(tok in h for tok in tokens):
            for role in roles:
                if role not in matched:
                    matched.append(role)
    # Unknown hint → no catalog roles; synthesizer emits unsupported stub with origin
    return matched


def propose_agents_from_inventory(inv: CompanyInventory) -> list[AgentProposal]:
    """
    Propose agents from inventory.

    Floor: honor attention.recommended_agent / need_attention nodes.
    Ceiling: never — always run full catalog (+ optional LLM) discovery after.
    """
    floor = _propose_from_recommendations(inv)
    if llm_configured():
        try:
            discovered = _propose_via_llm(inv)
        except Exception:  # noqa: BLE001
            discovered = _propose_via_catalog(inv)
    else:
        discovered = _propose_via_catalog(inv)
    return _merge_proposals(floor, discovered)


def _merge_proposals(
    floor: list[AgentProposal], discovered: list[AgentProposal]
) -> list[AgentProposal]:
    """Floor first; discovery adds extras. Same (role, product) keeps floor origin."""
    by_key: dict[tuple[str, str | None], AgentProposal] = {}
    for p in floor:
        by_key[(p.role, p.workspace_product)] = p
    for p in discovered:
        key = (p.role, p.workspace_product)
        if key in by_key:
            existing = by_key[key]
            # Prefer recommendation origin paths; keep discovery rationale append
            paths = list(dict.fromkeys([*existing.origin_paths, *p.origin_paths]))
            existing.origin_paths = paths[:16]
            signals = list(dict.fromkeys([*existing.origin_signals, *p.origin_signals]))
            existing.origin_signals = signals[:16]
            if p.rationale and p.rationale not in existing.rationale:
                existing.rationale = f"{existing.rationale} | {p.rationale}"
            continue
        by_key[key] = p
    return list(by_key.values())


def _attention_hits(inv: CompanyInventory) -> list[InventoryResource]:
    hits: list[InventoryResource] = []
    for r in inv.resources:
        attn = (r.attrs or {}).get("attention") or {}
        recommended = attn.get("recommended_agent") if isinstance(attn, dict) else None
        need = bool((r.attrs or {}).get("need_attention")) or (
            isinstance(attn, dict)
            and (attn.get("required") is True or bool(recommended))
        )
        if recommended or need:
            hits.append(r)
    return hits


def _propose_from_recommendations(inv: CompanyInventory) -> list[AgentProposal]:
    """Must-floor: every recommended_agent / attention hit yields ≥1 grounded proposal."""
    proposals: list[AgentProposal] = []
    available = inv.availability.available
    catalog_by_role = {e["role"]: e for e in SPECIALIZATION_CATALOG}
    products = _products(inv)

    for r in _attention_hits(inv):
        attn = (r.attrs or {}).get("attention") or {}
        hint = ""
        if isinstance(attn, dict):
            hint = str(attn.get("recommended_agent") or "").strip()
        product = r.owner_product or products[0]
        roles = map_recommended_hint_to_roles(hint) if hint else []

        # If hint empty but need_attention: pick roles from resource kind / source
        if not roles:
            kind = r.kind
            if kind == "repo" or (r.attrs or {}).get("source_type") == "github":
                roles = ["GitHubIssueManagerAgent"]
            elif kind in ("email_group", "email") or (r.attrs or {}).get("source_type") == "mail":
                roles = ["GmailCommsAgent"]
            elif kind == "calendar":
                roles = ["CalendarSchedulerAgent"]
            elif kind == "jira_project":
                roles = ["JiraSyncAgent"]

        if roles:
            for role in roles:
                entry = catalog_by_role.get(role)
                if not entry:
                    continue
                system = entry["system"]
                # Product scoping: only when inventory supports that system/resource
                if not (
                    _has_resource(inv, product, entry["requires_resource"])
                    or _system_mentioned(inv, system)
                ):
                    # Still emit unsupported stub covering the hint origin
                    proposals.append(
                        AgentProposal(
                            name=f"{product} {hint or role} (ungrounded)",
                            role=role,
                            system_key=system,
                            mission=entry["mission"],
                            tool_scope=[],
                            workspace_product=product,
                            status="unsupported",
                            activation="blocked_missing_connector",
                            origin_paths=[r.evidence_path],
                            origin_signals=[
                                f"recommended_agent:{hint or 'attention'}",
                                f"node:{r.name}",
                            ],
                            rationale=(
                                f"Recommendation floor for hint={hint!r}; "
                                f"no in-product inventory for {system}."
                            ),
                        )
                    )
                    continue
                executable = system in available and system in EXECUTABLE_SYSTEMS
                proposals.append(
                    AgentProposal(
                        name=entry["name_template"].format(product=product),
                        role=role,
                        system_key=system,
                        mission=entry["mission"],
                        tool_scope=list(entry["tool_scope"]) if executable else [],
                        workspace_product=product,
                        status="idle" if executable else "unsupported",
                        activation="ready" if executable else "blocked_missing_connector",
                        origin_paths=[r.evidence_path],
                        origin_signals=[
                            f"recommended_agent:{hint or 'attention'}",
                            f"node:{r.name}",
                        ],
                        rationale=(
                            f"Recommendation floor: mapped hint={hint!r} → {role} "
                            f"(must, not exclusive)."
                        ),
                        job_types=list(entry["job_types"]) if executable else [],
                        default_guardrails=list(entry["guardrails"]) if executable else [],
                    )
                )
            continue

        # Unknown hint string → unsupported stub with origin (never fake executor named hint)
        system_guess = (hint or "unknown").lower().replace(" ", "_")[:64]
        proposals.append(
            AgentProposal(
                name=f"{product} {hint or 'Attention'} Automation",
                role=f"{(hint or 'Attention').title().replace(' ', '')}Agent",
                system_key=system_guess if system_guess not in EXECUTABLE_SYSTEMS else "unknown",
                mission=(
                    f"Cover attention recommendation {hint!r} once a matching "
                    "connector/specialization exists."
                ),
                tool_scope=[],
                workspace_product=product,
                status="unsupported",
                activation="blocked_missing_connector",
                origin_paths=[r.evidence_path],
                origin_signals=[f"recommended_agent:{hint}", "unsupported"],
                rationale=f"Hint {hint!r} not mappable to v1 catalog; unsupported stub.",
            )
        )
    return proposals


def _propose_via_catalog(inv: CompanyInventory) -> list[AgentProposal]:
    proposals: list[AgentProposal] = []
    available = inv.availability.available

    for product in _products(inv):
        for entry in SPECIALIZATION_CATALOG:
            system = entry["system"]
            req = entry["requires_resource"]
            system_hits = _system_mentioned(inv, system)
            has_res = _has_resource(inv, product, req)
            # Instantiate specialization only when inventory shows the system or required resources
            if not (has_res or system_hits):
                continue
            executable = system in available and system in EXECUTABLE_SYSTEMS
            paths = [r.evidence_path for r in system_hits]
            paths += [
                r.evidence_path
                for r in inv.resources
                if r.kind == req and (r.owner_product in (None, product))
            ]
            proposals.append(
                AgentProposal(
                    name=entry["name_template"].format(product=product),
                    role=entry["role"],
                    system_key=system,
                    mission=entry["mission"],
                    tool_scope=list(entry["tool_scope"]) if executable else [],
                    workspace_product=product,
                    status="idle" if executable else "unsupported",
                    activation="ready" if executable else "blocked_missing_connector",
                    origin_paths=paths[:12],
                    origin_signals=[f"system:{system}", f"resource:{req}"],
                    rationale=(
                        f"Catalog specialization for {system} grounded in inventory "
                        f"(available={system in available})."
                    ),
                    job_types=list(entry["job_types"]) if executable else [],
                    default_guardrails=list(entry["guardrails"]) if executable else [],
                )
            )

    # Unsupported stubs for non-executable systems named in inventory
    seen_unsupported: set[tuple[str | None, str]] = set()
    for r in inv.resources:
        if r.kind != "system":
            continue
        if r.name in EXECUTABLE_SYSTEMS:
            # If executable system mentioned but connector unavailable → unsupported stub
            if r.name not in available:
                key = (r.owner_product, r.name)
                if key in seen_unsupported:
                    continue
                seen_unsupported.add(key)
                product = r.owner_product or (_products(inv)[0])
                proposals.append(
                    AgentProposal(
                        name=f"{product} {r.name.title()} Automation",
                        role=f"{r.name.title()}Agent",
                        system_key=r.name,
                        mission=f"Automate {r.name} workflows once a connector is available.",
                        tool_scope=[],
                        workspace_product=product,
                        status="unsupported",
                        activation="blocked_missing_connector",
                        origin_paths=[r.evidence_path],
                        origin_signals=[f"system:{r.name}", "connector:missing"],
                        rationale=f"System {r.name} present in KG but connector not available.",
                    )
                )
            continue
        key = (r.owner_product, r.name)
        if key in seen_unsupported:
            continue
        seen_unsupported.add(key)
        product = r.owner_product or (_products(inv)[0])
        proposals.append(
            AgentProposal(
                name=f"{product} {r.name.title()} Automation",
                role=f"{r.name.title()}Agent",
                system_key=r.name,
                mission=f"Discovered {r.name} automation opportunity; blocked until connector exists.",
                tool_scope=[],
                workspace_product=product,
                status="unsupported",
                activation="blocked_missing_connector",
                origin_paths=[r.evidence_path],
                origin_signals=[f"system:{r.name}", "unsupported"],
                rationale=f"KG names {r.name}; no v1 write tools — unsupported stub.",
            )
        )

    # Always include ValidationAgent (read-only) when any executable system exists
    if available:
        proposals.append(
            AgentProposal(
                name="Validation Agent",
                role="ValidationAgent",
                system_key="validation",
                mission="Re-query external systems to verify evidence; emit PASS/FAIL/NO_EVIDENCE.",
                tool_scope=["validation.read"],
                workspace_product=None,
                status="idle",
                activation="ready",
                origin_paths=["$.platform.validation"],
                origin_signals=["role:ValidationAgent"],
                rationale="Authority-required read-only validator.",
                job_types=[],
                default_guardrails=[
                    {"tool": "validation.read", "mode": "allow", "label": "Read-only validation"},
                ],
            )
        )

    return proposals


def _propose_via_llm(inv: CompanyInventory) -> list[AgentProposal]:
    """LLM proposes specializations; still constrained to catalog + inventory systems."""
    try:
        from aip.llm.client import chat_completion_json
    except ImportError:
        return _propose_via_catalog(inv)

    catalog_roles = [e["role"] for e in SPECIALIZATION_CATALOG] + ["ValidationAgent"]
    systems = sorted({r.name for r in inv.resources if r.kind == "system"})
    products = _products(inv)
    prompt = (
        "You propose automation agent specializations for a company knowledge graph.\n"
        "Return JSON: {\"agents\":[{\"role\":...,\"system_key\":...,\"product\":...,\"mission\":...,"
        "\"rationale\":...}]}.\n"
        f"Allowed roles: {catalog_roles}. You may also propose unsupported stubs for named systems "
        f"not in {sorted(EXECUTABLE_SYSTEMS)}.\n"
        f"Products: {products}. Systems in inventory: {systems}. "
        f"Available connectors now: {sorted(inv.availability.available)}.\n"
        "Do not invent products/repos/systems not in the inventory. "
        "Recommendations are a floor — still propose all justified catalog specializations."
    )
    try:
        data = chat_completion_json(
            system="You output only valid JSON.",
            user=prompt,
            temperature=0.2,
        )
    except Exception:  # noqa: BLE001
        return _propose_via_catalog(inv)
    if not isinstance(data, dict):
        return _propose_via_catalog(inv)
    # Merge LLM meaning with catalog tools via auditor-friendly proposals
    base = {(p.role, p.workspace_product): p for p in _propose_via_catalog(inv)}
    for row in data.get("agents") or []:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "")
        product = row.get("product")
        key = (role, product)
        if key in base:
            base[key].rationale = str(row.get("rationale") or base[key].rationale)
            if row.get("mission"):
                base[key].mission = str(row["mission"])
            continue
        # Unsupported / extra system stub
        system = str(row.get("system_key") or "unknown")
        executable = system in inv.availability.available and system in EXECUTABLE_SYSTEMS
        base[key] = AgentProposal(
            name=f"{product or 'Company'} {role}",
            role=role or f"{system.title()}Agent",
            system_key=system,
            mission=str(row.get("mission") or ""),
            tool_scope=[],
            workspace_product=str(product) if product else None,
            status="idle" if executable else "unsupported",
            activation="ready" if executable else "blocked_missing_connector",
            origin_signals=["llm:proposal"],
            rationale=str(row.get("rationale") or "LLM proposal"),
        )
    return list(base.values())


def synthesized_at() -> str:
    return datetime.now(timezone.utc).isoformat()

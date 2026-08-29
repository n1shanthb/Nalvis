"""Deterministic auditor — groundedness gate for agent proposals."""

from __future__ import annotations

from dataclasses import dataclass

from aip.evidence.contracts import EXECUTABLE_SYSTEMS, has_evidence_contract
from aip.kg.inventory import CompanyInventory
from aip.kg.synthesizer import AgentProposal, SPECIALIZATION_CATALOG


@dataclass
class AuditResult:
    accepted: list[AgentProposal]
    rejected: list[tuple[AgentProposal, str]]


_CATALOG_BY_ROLE = {e["role"]: e for e in SPECIALIZATION_CATALOG}


def audit_agent_proposals(inv: CompanyInventory, proposals: list[AgentProposal]) -> AuditResult:
    accepted: list[AgentProposal] = []
    rejected: list[tuple[AgentProposal, str]] = []
    products = set(inv.products) | {"default"}
    inventory_systems = {r.name for r in inv.resources if r.kind == "system"}
    available = inv.availability.available

    for p in proposals:
        # Product must exist when claimed
        if p.workspace_product and p.workspace_product not in products and inv.products:
            rejected.append((p, f"product {p.workspace_product} not in inventory"))
            continue

        if p.role == "ValidationAgent":
            if not available:
                rejected.append((p, "no available connectors to validate against"))
                continue
            p.tool_scope = ["validation.read"]
            p.status = "idle"
            p.activation = "ready"
            accepted.append(p)
            continue

        # Executable specializations must match catalog + available connector
        if p.role in _CATALOG_BY_ROLE:
            entry = _CATALOG_BY_ROLE[p.role]
            system = entry["system"]
            p.system_key = system
            if system not in inventory_systems and not any(
                r.kind == entry["requires_resource"] for r in inv.resources
            ):
                rejected.append((p, f"no inventory support for {system}/{entry['requires_resource']}"))
                continue
            if system not in available:
                p.status = "unsupported"
                p.activation = "blocked_missing_connector"
                p.tool_scope = []
                p.job_types = []
            else:
                p.status = "idle"
                p.activation = "ready"
                p.tool_scope = list(entry["tool_scope"])
                p.job_types = list(entry["job_types"])
                p.default_guardrails = list(entry["guardrails"])
                for jt in p.job_types:
                    if not has_evidence_contract(jt):
                        rejected.append((p, f"job_type {jt} lacks evidence contract"))
                        break
                else:
                    accepted.append(p)
                continue
            accepted.append(p)
            continue

        # Non-catalog → must be unsupported stub for a named inventory system
        if p.system_key in EXECUTABLE_SYSTEMS and p.system_key in available:
            rejected.append((p, "non-catalog executable agent rejected (use catalog roles)"))
            continue
        if p.system_key and p.system_key not in inventory_systems:
            rejected.append((p, f"system {p.system_key} not in inventory"))
            continue
        p.status = "unsupported"
        p.activation = "blocked_missing_connector"
        p.tool_scope = []
        p.job_types = []
        accepted.append(p)

    return AuditResult(accepted=accepted, rejected=rejected)

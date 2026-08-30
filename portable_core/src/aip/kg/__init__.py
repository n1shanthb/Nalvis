"""KG package — deterministic inventory + LLM/catalog synthesis + auditor."""

from aip.kg.auditor import audit_agent_proposals
from aip.kg.inventory import build_inventory_from_kg, parse_preview_from_inventory
from aip.kg.synthesizer import propose_agents_from_inventory

__all__ = [
    "audit_agent_proposals",
    "build_inventory_from_kg",
    "parse_preview_from_inventory",
    "propose_agents_from_inventory",
]

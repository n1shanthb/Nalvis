"""Deterministic KG inventory — facts only (Authority LLM vs deterministic split)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aip.evidence.contracts import EXECUTABLE_SYSTEMS, UNSUPPORTED_SYSTEM_ALIASES


@dataclass
class InventoryResource:
    kind: str  # product|repo|jira_project|calendar|email_group|system|stakeholder
    name: str
    owner_product: str | None = None
    evidence_path: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorAvailability:
    """What systems are actually executable right now (credentials + flags)."""

    available: set[str] = field(default_factory=set)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyInventory:
    company_name: str
    resources: list[InventoryResource]
    products: list[str]
    availability: ConnectorAvailability
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def probe_connector_availability() -> ConnectorAvailability:
    """Deterministic: which v1 connectors are configured/enabled now."""
    from aip.config import settings
    from aip.connectors import smoke as connector_smoke

    snap = connector_smoke.health_snapshot()
    available: set[str] = set()
    details: dict[str, Any] = {}

    gh = snap.get("github") or {}
    if gh.get("app_configured") or gh.get("token_resolvable"):
        available.add("github")
    details["github"] = gh

    jira = snap.get("jira") or {}
    if jira.get("token_configured") and jira.get("mcp_enabled"):
        available.add("jira")
    details["jira"] = jira

    gmail = snap.get("gmail") or {}
    if bool(gmail.get("configured")) and bool(gmail.get("enabled")):
        available.add("gmail")
    details["gmail"] = gmail

    cal = snap.get("calendar") or {}
    if bool(cal.get("configured")) and bool(cal.get("enabled")):
        available.add("calendar")
    details["calendar"] = cal
    details["settings_flags"] = {
        "github_mcp": settings.connected_system_github_mcp_enabled,
        "jira_mcp": settings.connected_system_jira_mcp_enabled,
        "gmail": settings.connected_system_gmail_enabled,
        "calendar": settings.connected_system_calendar_enabled,
    }
    return ConnectorAvailability(available=available, details=details)


def _normalize_system_name(name: str) -> str | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in EXECUTABLE_SYSTEMS:
        return key
    if key in UNSUPPORTED_SYSTEM_ALIASES:
        return UNSUPPORTED_SYSTEM_ALIASES[key]
    for alias, canon in UNSUPPORTED_SYSTEM_ALIASES.items():
        if alias in key:
            return canon
    return key.replace(" ", "_")


def build_inventory_from_kg(raw_text: str) -> CompanyInventory:
    """Parse/validate KG JSON into inventory of what exists + ownership + evidence pointers."""
    warnings: list[str] = []
    availability = probe_connector_availability()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return _inventory_from_text(raw_text, availability)

    if not isinstance(data, dict):
        warnings.append("KG root must be an object")
        data = {}

    company = str(data.get("company") or data.get("company_name") or data.get("name") or "").strip()
    resources: list[InventoryResource] = []
    products: list[str] = []

    product_rows = data.get("products") or data.get("workspaces") or []
    if not isinstance(product_rows, list):
        warnings.append("products must be a list")
        product_rows = []

    for i, prod in enumerate(product_rows):
        if not isinstance(prod, dict):
            warnings.append(f"products[{i}] skipped (not object)")
            continue
        pname = str(prod.get("name") or prod.get("product") or f"product-{i}").strip()
        products.append(pname)
        base = f"$.products[{i}]"
        resources.append(
            InventoryResource(kind="product", name=pname, owner_product=pname, evidence_path=base)
        )
        for j, repo in enumerate(prod.get("repos") or prod.get("github_repos") or []):
            resources.append(
                InventoryResource(
                    kind="repo",
                    name=str(repo).strip(),
                    owner_product=pname,
                    evidence_path=f"{base}.repos[{j}]",
                )
            )
        for j, key in enumerate(prod.get("jira") or prod.get("jira_projects") or []):
            resources.append(
                InventoryResource(
                    kind="jira_project",
                    name=str(key).strip(),
                    owner_product=pname,
                    evidence_path=f"{base}.jira[{j}]",
                )
            )
        for j, cal in enumerate(prod.get("calendars") or []):
            resources.append(
                InventoryResource(
                    kind="calendar",
                    name=str(cal).strip(),
                    owner_product=pname,
                    evidence_path=f"{base}.calendars[{j}]",
                )
            )
        for j, eg in enumerate(prod.get("email_groups") or prod.get("comms") or []):
            resources.append(
                InventoryResource(
                    kind="email_group",
                    name=str(eg).strip(),
                    owner_product=pname,
                    evidence_path=f"{base}.email_groups[{j}]",
                )
            )
        # Named external systems under product
        for j, sys_name in enumerate(prod.get("systems") or prod.get("integrations") or []):
            canon = _normalize_system_name(str(sys_name))
            if canon:
                resources.append(
                    InventoryResource(
                        kind="system",
                        name=canon,
                        owner_product=pname,
                        evidence_path=f"{base}.systems[{j}]",
                        attrs={"raw": str(sys_name)},
                    )
                )

    for i, sys_name in enumerate(data.get("systems") or data.get("external_systems") or []):
        canon = _normalize_system_name(str(sys_name) if not isinstance(sys_name, dict) else str(sys_name.get("name") or ""))
        if canon:
            resources.append(
                InventoryResource(
                    kind="system",
                    name=canon,
                    owner_product=None,
                    evidence_path=f"$.systems[{i}]",
                )
            )

    for i, stake in enumerate(data.get("stakeholders") or []):
        resources.append(
            InventoryResource(
                kind="stakeholder",
                name=str(stake).strip(),
                evidence_path=f"$.stakeholders[{i}]",
            )
        )

    # Infer system presence from resource kinds (facts, not meaning)
    if any(r.kind == "repo" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="github", evidence_path="$.inferred.repos→github")
        )
    if any(r.kind == "jira_project" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="jira", evidence_path="$.inferred.jira→jira")
        )
    if any(r.kind == "email_group" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="gmail", evidence_path="$.inferred.email→gmail")
        )
    if any(r.kind == "calendar" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="calendar", evidence_path="$.inferred.calendar→calendar")
        )

    if not products:
        warnings.append("No products found in KG")

    return CompanyInventory(
        company_name=company,
        resources=resources,
        products=products,
        availability=availability,
        warnings=warnings,
        raw=data if isinstance(data, dict) else {},
    )


def _inventory_from_text(raw_text: str, availability: ConnectorAvailability) -> CompanyInventory:
    warnings = ["Input was not valid JSON — used heuristic text inventory (facts only)"]
    resources: list[InventoryResource] = []
    for m in re.finditer(r"\b([\w.-]+/[\w.-]+)\b", raw_text):
        resources.append(InventoryResource(kind="repo", name=m.group(1), evidence_path="$.text.repo"))
    for m in re.finditer(r"\b([A-Z][A-Z0-9]{1,9})\b", raw_text):
        resources.append(
            InventoryResource(kind="jira_project", name=m.group(1), evidence_path="$.text.jira")
        )
    for alias in list(UNSUPPORTED_SYSTEM_ALIASES.keys()) + list(EXECUTABLE_SYSTEMS):
        if re.search(rf"\b{re.escape(alias)}\b", raw_text, re.I):
            canon = _normalize_system_name(alias) or alias
            resources.append(
                InventoryResource(kind="system", name=canon, evidence_path="$.text.system")
            )
    return CompanyInventory(
        company_name="",
        resources=resources,
        products=[],
        availability=availability,
        warnings=warnings,
        raw={},
    )


def parse_preview_from_inventory(inv: CompanyInventory) -> dict[str, Any]:
    repos = [r.name for r in inv.resources if r.kind == "repo"]
    jira = [r.name for r in inv.resources if r.kind == "jira_project"]
    cals = [r.name for r in inv.resources if r.kind == "calendar"]
    emails = [r.name for r in inv.resources if r.kind == "email_group"]
    stakes = [r.name for r in inv.resources if r.kind == "stakeholder"]
    return {
        "products": list(inv.products),
        "workspacesDerived": len(inv.products),
        "repos": repos,
        "jiraProjects": jira,
        "calendars": cals,
        "emailGroups": emails,
        "stakeholders": stakes,
        "systems": sorted({r.name for r in inv.resources if r.kind == "system"}),
        "availableConnectors": sorted(inv.availability.available),
        "warnings": list(inv.warnings),
    }

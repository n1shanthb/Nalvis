"""Deterministic KG inventory — facts only (Authority LLM vs deterministic split).

Supports:
- Flat `{company, products[]}` paste format (secondary)
- Graph KG `{nodes[], edges[]|links[]}` as in ex1/ex2 (primary)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aip.evidence.contracts import EXECUTABLE_SYSTEMS, UNSUPPORTED_SYSTEM_ALIASES


@dataclass
class InventoryResource:
    kind: str  # product|repo|jira_project|calendar|email_group|email|system|stakeholder|document|other
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

    # Graph primary: nodes + edges|links
    if isinstance(data.get("nodes"), list):
        return _inventory_from_graph(data, availability)

    return _inventory_from_flat(data, availability, warnings)


def _inventory_from_flat(
    data: dict[str, Any],
    availability: ConnectorAvailability,
    warnings: list[str],
) -> CompanyInventory:
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
        jpk = prod.get("jira_project_key")
        if jpk:
            resources.append(
                InventoryResource(
                    kind="jira_project",
                    name=str(jpk).strip(),
                    owner_product=pname,
                    evidence_path=f"{base}.jira_project_key",
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
        for alias_key, kind_hint in (
            ("slack_channels", "slack"),
            ("aws_accounts", "aws"),
            ("linear_team_key", "linear"),
            ("notion_pages", "notion"),
        ):
            vals = prod.get(alias_key)
            if vals is None:
                continue
            if not isinstance(vals, list):
                vals = [vals]
            for j, v in enumerate(vals):
                resources.append(
                    InventoryResource(
                        kind="system",
                        name=kind_hint,
                        owner_product=pname,
                        evidence_path=f"{base}.{alias_key}[{j}]",
                        attrs={"raw": str(v)},
                    )
                )

    for i, sys_name in enumerate(data.get("systems") or data.get("external_systems") or []):
        canon = _normalize_system_name(
            str(sys_name) if not isinstance(sys_name, dict) else str(sys_name.get("name") or "")
        )
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

    _infer_systems_from_resources(resources)

    if not products:
        warnings.append("No products found in KG")

    return CompanyInventory(
        company_name=company,
        resources=resources,
        products=products,
        availability=availability,
        warnings=warnings,
        raw=data,
    )


def _node_name(node: dict[str, Any]) -> str:
    identity = node.get("identity") if isinstance(node.get("identity"), dict) else {}
    return str(
        node.get("name") or identity.get("name") or node.get("id") or "unnamed"
    ).strip()


def _node_entity_type(node: dict[str, Any]) -> str:
    identity = node.get("identity") if isinstance(node.get("identity"), dict) else {}
    classification = node.get("classification") if isinstance(node.get("classification"), dict) else {}
    return str(
        node.get("type") or identity.get("entity_type") or classification.get("type") or ""
    ).strip().lower()


def _node_source_type(node: dict[str, Any]) -> str:
    source = node.get("source") if isinstance(node.get("source"), dict) else {}
    return str(node.get("source_type") or source.get("source_type") or "").strip().lower()


def _repo_full_name(node: dict[str, Any]) -> str | None:
    """Infer owner/repo from summary/external fields when present."""
    summary = str(node.get("summary") or "")
    semantic = node.get("semantic") if isinstance(node.get("semantic"), dict) else {}
    summary = summary or str(semantic.get("summary") or "")
    name = _node_name(node)
    blob = f"{name}\n{summary}"

    # Strict patterns only — bare owner/repo over-matches English "A/B" phrases in Entity graphs.
    for pat in (
        r"github\.com[/:]([\w][\w.-]*/[\w][\w.-]*?)(?:\.git)?(?=[\s/,)\]\"']|$)",
        r"GitHub Repository\s+([\w][\w.-]*/[\w][\w.-]*)",
        r"https?://github\.com/([\w][\w.-]*/[\w][\w.-]*?)(?:\.git)?(?=[\s/,)\]\"']|$)",
    ):
        m = re.search(pat, blob, re.I)
        if m:
            slug = _clean_repo_slug(m.group(1))
            if _looks_like_github_repo(slug):
                return slug

    source = node.get("source") if isinstance(node.get("source"), dict) else {}
    for cand in (
        source.get("external_id"),
        source.get("source_id"),
        node.get("source_id"),
        name if "/" in name else None,
    ):
        ext = str(cand or "").strip()
        if not ext or ext.startswith("github:repo:"):
            continue
        if _looks_like_github_repo(ext):
            return _clean_repo_slug(ext)
    return None


def _clean_repo_slug(slug: str) -> str:
    s = slug.strip().removesuffix(".git")
    return s


def _looks_like_github_repo(slug: str) -> bool:
    s = _clean_repo_slug(slug)
    if s.count("/") != 1:
        return False
    owner, repo = s.split("/", 1)
    if not owner or not repo:
        return False
    # Reject hostnames and file paths
    if "." in owner or "." in repo:
        return False
    if any(repo.lower().endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".md", ".json", ".css", ".html")):
        return False
    banned = {
        "http",
        "https",
        "www",
        "agent",
        "src",
        "lib",
        "app",
        "apps",
        "tests",
        "test",
        "signup",
        "login",
        "workspace",
        "workspaces",
        "task",
        "event",
        "file",
        "directory",
        "vt",
        "ansi-compatible",
        "incorrectly",
        "ep-xxx",
    }
    if owner.lower() in banned or repo.lower() in banned:
        return False
    return bool(re.match(r"^[\w-]+$", owner) and re.match(r"^[\w-]+$", repo))


def _is_repo_node(et: str, src: str) -> bool:
    if et in ("gitrepository", "repository", "repo", "git_repository"):
        return True
    # Flat ex1-style: Entity + source_type github often carries repo facts in summary
    if src == "github" and et in ("repository", "gitrepository", "repo", "", "entity"):
        return True
    return False


def _is_company_entity_type(et: str) -> bool:
    return et in ("organization", "org", "company")


def _is_workspace_entity_type(et: str) -> bool:
    return et in ("product", "workspace", "project")


def _inventory_from_graph(
    data: dict[str, Any],
    availability: ConnectorAvailability,
) -> CompanyInventory:
    warnings: list[str] = []
    nodes = data.get("nodes") or []
    edges = data.get("edges") or data.get("links") or []
    if not isinstance(nodes, list):
        nodes = []
        warnings.append("nodes must be a list")
    if not isinstance(edges, list):
        edges = []
        warnings.append("edges/links must be a list")

    company = str(data.get("company") or data.get("company_name") or data.get("name") or "").strip()
    resources: list[InventoryResource] = []
    products: list[str] = []
    product_set: set[str] = set()
    seen_repos: set[str] = set()

    by_id: dict[str, dict[str, Any]] = {}
    for n in nodes:
        if isinstance(n, dict) and n.get("id"):
            by_id[str(n["id"])] = n

    for n in nodes:
        if not isinstance(n, dict):
            continue
        et = _node_entity_type(n)
        name = _node_name(n)
        if _is_company_entity_type(et):
            if name and not company:
                company = name
            continue
        if _is_workspace_entity_type(et):
            if name and name not in product_set:
                product_set.add(name)
                products.append(name)

    for e in edges:
        if not isinstance(e, dict):
            continue
        rel = str(e.get("relation_type") or e.get("type") or "").upper()
        if rel in ("BELONGS_TO", "USES", "PART_OF", "OWNED_BY"):
            target = by_id.get(str(e.get("target") or ""))
            if not target:
                continue
            tet = _node_entity_type(target)
            pname = _node_name(target)
            if _is_company_entity_type(tet):
                if pname and not company:
                    company = pname
                continue
            if _is_workspace_entity_type(tet):
                if pname and pname not in product_set:
                    product_set.add(pname)
                    products.append(pname)

    # Pass 1: collect repos from *any* github-linked node (ex1 flat Entity graph)
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        et = _node_entity_type(node)
        src = _node_source_type(node)
        path = f"$.nodes[id={node.get('id') or i}]"
        slug = _repo_full_name(node)
        if slug and slug not in seen_repos and (src == "github" or _is_repo_node(et, src) or "github" in str(node.get("summary") or "").lower()):
            seen_repos.add(slug)
            resources.append(
                InventoryResource(
                    kind="repo",
                    name=slug,
                    owner_product=None,  # assigned after products known
                    evidence_path=f"{path}.repo",
                    attrs={"entity_type": et, "source_type": src, "node_id": str(node.get("id") or i)},
                )
            )
            resources.append(
                InventoryResource(
                    kind="system",
                    name="github",
                    evidence_path=f"{path}.source_type",
                )
            )
        elif src == "github":
            resources.append(
                InventoryResource(
                    kind="system",
                    name="github",
                    evidence_path=f"{path}.source_type",
                )
            )

    # Products: prefer typed products; else repo project names; else group_id
    if not products:
        for slug in sorted(seen_repos):
            proj = slug.split("/", 1)[-1]
            if proj and proj not in product_set:
                product_set.add(proj)
                products.append(proj)
    if not products:
        gids = sorted(
            {
                str(n.get("group_id")).strip()
                for n in nodes
                if isinstance(n, dict) and n.get("group_id")
            }
        )
        if gids:
            products = gids
            product_set.update(gids)
        else:
            products = ["default"]
            product_set.add("default")

    if not company and products:
        company = products[0]
    if not company:
        gids = [
            str(n.get("group_id")).strip()
            for n in nodes
            if isinstance(n, dict) and n.get("group_id")
        ]
        if gids:
            company = gids[0]

    for pname in products:
        resources.append(
            InventoryResource(
                kind="product",
                name=pname,
                owner_product=pname,
                evidence_path=f"$.graph.product:{pname}",
            )
        )

    # Assign repo ownership: match product name to repo suffix, else first product
    for r in resources:
        if r.kind != "repo" or r.owner_product:
            continue
        suffix = r.name.split("/", 1)[-1].lower()
        matched = next((p for p in products if p.lower() == suffix or suffix in p.lower()), None)
        r.owner_product = matched or products[0]

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            warnings.append(f"nodes[{i}] skipped (not object)")
            continue
        nid = str(node.get("id") or i)
        path = f"$.nodes[id={nid}]"
        name = _node_name(node)
        et = _node_entity_type(node)
        src = _node_source_type(node)
        gid = str(node.get("group_id") or "").strip() or None
        owner = gid if gid in product_set else (products[0] if products else None)
        # Prefer product matching repo suffix when this node yielded a repo
        slug = _repo_full_name(node)
        if slug:
            suf = slug.split("/", 1)[-1].lower()
            owner = next((p for p in products if p.lower() == suf), owner)
        attention = node.get("attention") if isinstance(node.get("attention"), dict) else {}
        need_attention = bool(node.get("need_attention")) or bool(attention.get("required"))
        semantic = node.get("semantic") if isinstance(node.get("semantic"), dict) else {}
        attrs: dict[str, Any] = {
            "node_id": nid,
            "entity_type": et,
            "source_type": src,
            "attention": attention,
            "need_attention": need_attention,
            "summary": node.get("summary") or semantic.get("summary"),
        }

        kind = "other"
        resource_name = name
        # Repos already collected in pass 1 — skip duplicate kind=repo append
        if _is_repo_node(et, src) and slug:
            kind = "repo"
            resource_name = slug
            # still record attention-bearing node attrs via other path below only if needed
            if need_attention or attention.get("recommended_agent"):
                resources.append(
                    InventoryResource(
                        kind="other",
                        name=name,
                        owner_product=owner,
                        evidence_path=path,
                        attrs=attrs,
                    )
                )
            continue
        if et in ("email", "mail", "message") or src == "mail":
            kind = "email_group" if "@" in name else "email"
            summary = str(attrs.get("summary") or "")
            emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", summary)
            for j, em in enumerate(emails[:3]):
                resources.append(
                    InventoryResource(
                        kind="email_group",
                        name=em,
                        owner_product=owner,
                        evidence_path=f"{path}.summary.email[{j}]",
                        attrs={"from_node": nid},
                    )
                )
            resources.append(
                InventoryResource(
                    kind="system",
                    name="gmail",
                    owner_product=owner,
                    evidence_path=f"{path}.source_type",
                )
            )
        elif et in ("calendar", "event", "meeting"):
            kind = "calendar"
            resources.append(
                InventoryResource(
                    kind="system",
                    name="calendar",
                    owner_product=owner,
                    evidence_path=f"{path}.type",
                )
            )
        elif et in ("jiraproject", "jira", "ticket", "issue") or "jira" in et:
            kind = "jira_project"
            resources.append(
                InventoryResource(
                    kind="system",
                    name="jira",
                    owner_product=owner,
                    evidence_path=f"{path}.type",
                )
            )
        elif et in ("person", "user", "stakeholder", "developer"):
            kind = "stakeholder"
        elif et in ("document", "file", "policy", "commit", "gitfile", "gitcommit"):
            kind = "document" if et in ("document", "file", "policy", "gitfile") else "other"
        elif et in ("product", "workspace", "project", "organization", "org", "company"):
            kind = "product" if _is_workspace_entity_type(et) else "other"
            if _is_company_entity_type(et):
                kind = "other"
            resource_name = name

        blob = f"{name} {et} {src} {attrs.get('summary') or ''}".lower()
        for alias in list(UNSUPPORTED_SYSTEM_ALIASES.keys()) + list(EXECUTABLE_SYSTEMS):
            if re.search(rf"\b{re.escape(alias)}\b", blob):
                canon = _normalize_system_name(alias)
                if canon:
                    resources.append(
                        InventoryResource(
                            kind="system",
                            name=canon,
                            owner_product=owner,
                            evidence_path=f"{path}.text:{alias}",
                        )
                    )

        # Skip dumping every Entity as "other" when we already have github system — keep
        # attention nodes + non-github entities for auditor origin paths.
        if et == "entity" and src == "github" and not (need_attention or attention.get("recommended_agent")):
            continue

        resources.append(
            InventoryResource(
                kind=kind,
                name=resource_name,
                owner_product=owner,
                evidence_path=path,
                attrs=attrs,
            )
        )

    for alias_key, system in (
        ("jira_project_key", "jira"),
        ("linear_team_key", "linear"),
    ):
        if data.get(alias_key):
            resources.append(
                InventoryResource(
                    kind="jira_project" if system == "jira" else "system",
                    name=str(data[alias_key]),
                    evidence_path=f"$.{alias_key}",
                    attrs={"system": system},
                )
            )
            if system == "jira":
                resources.append(
                    InventoryResource(kind="system", name="jira", evidence_path=f"$.{alias_key}")
                )

    node_count = sum(1 for n in nodes if isinstance(n, dict))
    repo_count = sum(1 for r in resources if r.kind == "repo")
    if node_count >= 20 and repo_count == 0:
        warnings.append(
            f"Graph has {node_count} nodes but no owner/repo slugs found — "
            "summaries may lack github.com/org/repo; agents may be under-scoped"
        )
    elif node_count >= 50 and repo_count <= 1:
        warnings.append(
            f"Sparse repo extraction ({repo_count} from {node_count} nodes) — "
            "flat Entity graphs need github.com/org/repo in summaries"
        )

    _infer_systems_from_resources(resources)

    if not company and products:
        company = products[0]

    return CompanyInventory(
        company_name=company,
        resources=resources,
        products=products,
        availability=availability,
        warnings=warnings,
        raw=data,
    )


def _infer_systems_from_resources(resources: list[InventoryResource]) -> None:
    if any(r.kind == "repo" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="github", evidence_path="$.inferred.repos→github")
        )
    if any(r.kind == "jira_project" for r in resources):
        resources.append(
            InventoryResource(kind="system", name="jira", evidence_path="$.inferred.jira→jira")
        )
    if any(r.kind in ("email_group", "email") for r in resources):
        resources.append(
            InventoryResource(kind="system", name="gmail", evidence_path="$.inferred.email→gmail")
        )
    if any(r.kind == "calendar" for r in resources):
        resources.append(
            InventoryResource(
                kind="system", name="calendar", evidence_path="$.inferred.calendar→calendar"
            )
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
    emails = [r.name for r in inv.resources if r.kind in ("email_group", "email")]
    # Prefer actual addresses; thread subjects without @ are secondary noise in UI preview.
    emails = sorted({e for e in emails if "@" in e}) + [
        e for e in emails if "@" not in e and e not in {x for x in emails if "@" in x}
    ]
    stakes = [r.name for r in inv.resources if r.kind == "stakeholder"]
    attention = [
        {
            "name": r.name,
            "path": r.evidence_path,
            "recommended_agent": ((r.attrs or {}).get("attention") or {}).get("recommended_agent"),
        }
        for r in inv.resources
        if (r.attrs or {}).get("need_attention")
        or ((r.attrs or {}).get("attention") or {}).get("recommended_agent")
    ]
    return {
        "products": list(inv.products),
        "workspacesDerived": len(inv.products),
        "repos": repos,
        "jiraProjects": jira,
        "calendars": cals,
        "emailGroups": emails,
        "stakeholders": stakes,
        "systems": sorted({r.name for r in inv.resources if r.kind == "system"}),
        "attentionNodes": attention,
        "availableConnectors": sorted(inv.availability.available),
        "warnings": list(inv.warnings),
        "format": "graph" if isinstance(inv.raw.get("nodes"), list) else "flat",
    }

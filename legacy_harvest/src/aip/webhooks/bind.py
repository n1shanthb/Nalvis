"""Sync WebhookBinding rows from an AgentSpecification (no FastAPI)."""

from __future__ import annotations

from pathlib import Path

import yaml

from aip.contracts.specification import AgentSpecification
from aip.webhooks.catalog import WebhookCatalog
from aip.webhooks.match import connected_system_for_webhook, known_webhook_ids
from aip.webhooks.models import WebhookBinding


def is_fixture_spec(spec: AgentSpecification) -> bool:
    return str((spec.metadata or {}).get("source") or "").strip().lower() == "fixture"


def _load_spec_file(path: Path) -> AgentSpecification | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return AgentSpecification.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


def sync_spec_bindings(
    spec: AgentSpecification,
    catalog: WebhookCatalog | None = None,
) -> list[WebhookBinding]:
    """Replace this spec's bindings with trigger.webhook_ids. Skip fixture specs."""
    if is_fixture_spec(spec):
        return []
    webhooks = catalog or WebhookCatalog()
    webhooks.ensure_tables()
    webhooks.delete_bindings_for_spec(spec.spec_id)
    allowed = known_webhook_ids()
    out: list[WebhookBinding] = []
    meta = dict(spec.metadata or {})
    company_id = str(meta.get("company_id") or "").strip() or None
    project_id = str(meta.get("project_id") or "").strip() or None
    scope_level = str(meta.get("scope_level") or "").strip().lower()
    systems = [str(s).lower() for s in (meta.get("connected_system_ids") or [])]
    if not scope_level:
        scope_level = "project"
    discovered_from = str(meta.get("discovered_from") or "").strip()
    if scope_level == "project" and not project_id:
        project_id = discovered_from or spec.agent.org_id
    if not company_id:
        from aip.projects.models import DEFAULT_COMPANY_ID

        company_id = DEFAULT_COMPANY_ID
    for webhook_id in spec.trigger.webhook_ids or []:
        wid = (webhook_id or "").strip()
        if not wid or wid not in allowed:
            continue
        system_id = connected_system_for_webhook(wid)
        bind_scope = scope_level
        bind_project = project_id
        # Gmail ingress is one shared mailbox — bind each agent to its project only.
        if system_id == "gmail":
            bind_scope = "project"
            bind_project = (project_id or discovered_from or spec.agent.org_id or "").strip()
            if not bind_project:
                continue
        binding = WebhookBinding(
            webhook_id=wid,
            connected_system_id=system_id,
            spec_id=spec.spec_id,
            enabled=True,
            reason="spec.trigger.webhook_ids",
            company_id=company_id,
            project_id=None if bind_scope == "company" else bind_project,
            scope_level=bind_scope,
        )
        webhooks.upsert_binding(binding)
        out.append(binding)
    return out


def drop_spec_bindings(
    spec_id: str, catalog: WebhookCatalog | None = None
) -> None:
    webhooks = catalog or WebhookCatalog()
    webhooks.ensure_tables()
    webhooks.delete_bindings_for_spec(spec_id)


def company_bindings(
    system_id: str, catalog: WebhookCatalog | None = None
) -> list[WebhookBinding]:
    """Bindings for Connectors UI — omit lab fixture spec ids."""
    webhooks = catalog or WebhookCatalog()
    webhooks.ensure_tables()
    fixture_ids = _fixture_spec_ids()
    return [
        binding
        for binding in webhooks.list_bindings(system_id)
        if binding.spec_id not in fixture_ids
    ]


def sync_bindings_from_specs_dir(root: Path | None = None) -> None:
    """Rehydrate company bindings from active YAML. Never bind fixture specs."""
    from aip.config import settings

    directory = root or settings.specs_dir
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        spec = _load_spec_file(path)
        if spec is None:
            continue
        if is_fixture_spec(spec):
            drop_spec_bindings(spec.spec_id)
            continue
        sync_spec_bindings(spec)


def _fixture_spec_ids() -> set[str]:
    from aip.config import settings

    directory = settings.specs_dir
    if not directory.is_dir():
        return set()
    ids: set[str] = set()
    for path in list(directory.glob("*.yaml")) + list(directory.glob("*.yml")):
        spec = _load_spec_file(path)
        if spec is not None and is_fixture_spec(spec):
            ids.add(spec.spec_id)
    return ids

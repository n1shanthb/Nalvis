"""Sync WebhookBinding rows from an AgentSpecification (portable; no projects DB)."""

from __future__ import annotations

from pathlib import Path

import yaml

from aip.contracts.specification import AgentSpecification
from aip.webhooks.catalog import WebhookCatalog
from aip.webhooks.match import connected_system_for_webhook, known_webhook_ids
from aip.webhooks.models import WebhookBinding

DEFAULT_COMPANY_ID = "default"


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
    company_id = str(meta.get("company_id") or "").strip() or DEFAULT_COMPANY_ID
    project_id = str(meta.get("project_id") or "").strip() or None
    scope_level = str(meta.get("scope_level") or "").strip().lower() or "project"
    discovered_from = str(meta.get("discovered_from") or "").strip()
    if scope_level == "project" and not project_id:
        project_id = discovered_from or spec.agent.org_id
    for webhook_id in spec.trigger.webhook_ids or []:
        wid = (webhook_id or "").strip()
        if not wid or wid not in allowed:
            continue
        system_id = connected_system_for_webhook(wid)
        binding = WebhookBinding(
            webhook_id=wid,
            connected_system_id=system_id,
            spec_id=spec.spec_id,
            enabled=True,
            reason="synced_from_spec",
            company_id=company_id,
            project_id=project_id,
            scope_level=scope_level,
        )
        webhooks.upsert_binding(binding)
        out.append(binding)
    return out


def sync_spec_file(path: Path, catalog: WebhookCatalog | None = None) -> list[WebhookBinding]:
    spec = _load_spec_file(path)
    if spec is None:
        return []
    return sync_spec_bindings(spec, catalog=catalog)

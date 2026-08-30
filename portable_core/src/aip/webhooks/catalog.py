"""In-memory webhook catalog (no SQLModel / persistence)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aip.webhooks.github_inventory import github_webhook_seed
from aip.webhooks.gmail_inventory import gmail_webhook_seed
from aip.webhooks.jira_inventory import jira_webhook_seed
from aip.webhooks.models import EnterpriseWebhook, WebhookBinding, WebhookCatalogVersionRecord


class WebhookCatalog:
    """In-process webhook inventory + bindings (portable Phase 0A)."""

    def __init__(self) -> None:
        self._webhooks: dict[str, EnterpriseWebhook] = {}
        self._bindings: dict[str, WebhookBinding] = {}
        self._versions: dict[str, WebhookCatalogVersionRecord] = {}
        self._seeded = False

    def ensure_tables(self) -> None:
        """No-op for in-memory catalog (API compatibility with legacy callers)."""
        self.seed_defaults()

    def seed_defaults(self) -> None:
        if self._seeded:
            return
        for wh in (*github_webhook_seed(), *jira_webhook_seed(), *gmail_webhook_seed()):
            self._webhooks[f"{wh.connected_system_id}::{wh.id}"] = wh
        self._seeded = True

    def list_webhooks(self, connected_system_id: str | None = None) -> list[EnterpriseWebhook]:
        self.seed_defaults()
        out = list(self._webhooks.values())
        if connected_system_id:
            out = [w for w in out if w.connected_system_id == connected_system_id]
        return sorted(out, key=lambda w: (w.connected_system_id, w.id))

    def accept_inventory(
        self,
        connected_system_id: str,
        webhooks: list[EnterpriseWebhook],
    ) -> WebhookCatalogVersionRecord:
        self.seed_defaults()
        version = (self._versions.get(connected_system_id).version if connected_system_id in self._versions else 0) + 1
        # Replace system entries
        for key in [k for k in self._webhooks if k.startswith(f"{connected_system_id}::")]:
            del self._webhooks[key]
        for wh in webhooks:
            self._webhooks[f"{connected_system_id}::{wh.id}"] = wh
        record = WebhookCatalogVersionRecord(
            connected_system_id=connected_system_id,
            version=version,
            webhook_count=len(webhooks),
            accepted_at=datetime.now(timezone.utc),
        )
        self._versions[connected_system_id] = record
        return record

    def delete_bindings_for_spec(self, spec_id: str) -> None:
        self._bindings = {k: v for k, v in self._bindings.items() if v.spec_id != spec_id}

    def upsert_binding(self, binding: WebhookBinding) -> WebhookBinding:
        key = f"{binding.connected_system_id}::{binding.webhook_id}::{binding.spec_id}"
        self._bindings[key] = binding
        return binding

    def upsert_bindings(self, bindings: list[WebhookBinding]) -> None:
        for b in bindings:
            self.upsert_binding(b)

    def list_bindings(self, spec_id: str | None = None) -> list[WebhookBinding]:
        out = list(self._bindings.values())
        if spec_id:
            out = [b for b in out if b.spec_id == spec_id]
        return out

    def clear(self) -> None:
        self._webhooks.clear()
        self._bindings.clear()
        self._versions.clear()
        self._seeded = False

"""Stable webhook catalog / binding interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aip.webhooks.models import EnterpriseWebhook, WebhookBinding


@runtime_checkable
class WebhookCatalogPort(Protocol):
    def list_webhooks(self, connected_system_id: str | None = None) -> list[EnterpriseWebhook]: ...

    def upsert_bindings(self, bindings: list[WebhookBinding]) -> None: ...

    def list_bindings(self, spec_id: str | None = None) -> list[WebhookBinding]: ...


__all__ = ["EnterpriseWebhook", "WebhookBinding", "WebhookCatalogPort"]

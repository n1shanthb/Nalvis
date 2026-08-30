"""Static Gmail webhook inventory (seed for Webhook Catalog)."""

from __future__ import annotations

from aip.webhooks.models import EnterpriseWebhook


def gmail_webhook_seed(system_id: str = "gmail") -> list[EnterpriseWebhook]:
    return [
        EnterpriseWebhook(
            connected_system_id=system_id,
            id="gmail.message",
            event="gmail.message",
            action="",
            description="Inbound Gmail message (Pub/Sub watch or push)",
            capability_tags=["email", "inbox", "gmail"],
        )
    ]

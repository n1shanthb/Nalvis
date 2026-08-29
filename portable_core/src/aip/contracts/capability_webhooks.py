"""Future matcher contract: tools + webhooks assigned together.

The capability matcher (not implemented in this pass) should produce
`CapabilityWebhookRequirement` rows when an agent uses a Connected System
like GitHub MCP:

    CapabilityWebhookRequirement(
        capability_id="github_pr_review",
        connected_system_id="github",
        tool_names=["pull_request_read", "pull_request_review_write", ...],
        webhook_ids=["pull_request.opened", "pull_request.synchronize", ...],
    )

Today:
- Enterprise Tool Catalog = callable MCP/native tools
- Webhook Catalog = wake events
- WebhookBinding = temporary Spec routing until matcher writes bindings
"""

from aip.webhooks.models import CapabilityWebhookRequirement

__all__ = ["CapabilityWebhookRequirement"]

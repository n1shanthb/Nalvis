"""Static Jira Cloud webhook event inventory (seed for Webhook Catalog)."""

from __future__ import annotations

from aip.webhooks.models import EnterpriseWebhook

# Core events for event-driven issue triage / comment reply.
_JIRA_EVENTS: list[tuple[str, str]] = [
    ("jira:issue_created", "New Jira issue opened"),
    ("jira:issue_updated", "Jira issue fields or status changed"),
    ("comment_created", "Comment added on a Jira issue"),
    ("comment_updated", "Comment edited on a Jira issue"),
]


def jira_webhook_id(webhook_event: str) -> str:
    return (webhook_event or "unknown").strip()


def jira_webhook_seed(system_id: str = "jira") -> list[EnterpriseWebhook]:
    out: list[EnterpriseWebhook] = []
    for event_id, description in _JIRA_EVENTS:
        out.append(
            EnterpriseWebhook(
                connected_system_id=system_id,
                id=event_id,
                event=event_id,
                action="",
                description=description,
                capability_tags=["jira_triage", "jira_issue"],
            )
        )
    return out

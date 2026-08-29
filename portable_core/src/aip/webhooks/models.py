"""Webhook inventory models — parallel to Enterprise Tool Catalog (no execute)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EnterpriseWebhook(BaseModel):
    """One cataloged webhook event that can wake an agent."""

    connected_system_id: str
    id: str  # e.g. pull_request.opened
    event: str  # X-GitHub-Event
    action: str = ""  # payload.action when present
    description: str = ""
    capability_tags: list[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookCatalogVersionRecord(BaseModel):
    connected_system_id: str
    version: int
    webhook_count: int
    accepted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rejected: bool = False
    reject_reason: str | None = None


class WebhookBinding(BaseModel):
    """Matcher precursor: webhook_id → Spec (later agent_id)."""

    webhook_id: str
    connected_system_id: str = "github"
    spec_id: str
    enabled: bool = True
    reason: str = ""
    company_id: str | None = None
    project_id: str | None = None
    scope_level: str = "project"


class CapabilityWebhookRequirement(BaseModel):
    """Future matcher contract: tools + webhooks assigned together for a capability."""

    capability_id: str
    connected_system_id: str
    tool_names: list[str] = Field(default_factory=list)
    webhook_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 1.0
    policy_rule_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

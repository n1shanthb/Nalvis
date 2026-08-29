"""Jira MCP provider (seed drafts only; live MCP deferred to clean rebuild)."""

from __future__ import annotations

from aip.config import settings
from aip.connected_systems.models import (
    CatalogSource,
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
    TransportKind,
)

JIRA_SEED_TOOLS: list[DiscoveredToolDraft] = [
    DiscoveredToolDraft(
        name="jira_get_issue",
        description="Get a Jira issue by key",
        input_schema={
            "type": "object",
            "properties": {"issue_key": {"type": "string"}},
            "required": ["issue_key"],
        },
        permissions=["read"],
        toolset="jira",
        capability_tags=["jira_sync"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="jira_create_issue",
        description="Create a Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "project_key": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "issue_type": {"type": "string"},
            },
            "required": ["project_key", "summary"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_sync"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="jira_transition_issue",
        description="Transition a Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "issue_key": {"type": "string"},
                "transition_id": {"type": "string"},
            },
            "required": ["issue_key", "transition_id"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_sync"],
        department_tags=["engineering"],
    ),
]


class JiraProvider:
    """MCP-backed Jira provider — seed catalog for portable_core."""

    def __init__(self, *, use_seed_fallback: bool = True) -> None:
        self._connected = False
        self._use_seed_fallback = use_seed_fallback
        self._catalog_source = CatalogSource.UNAVAILABLE

    def metadata(self) -> ConnectedSystemMetadata:
        return ConnectedSystemMetadata(
            id="jira",
            provider="jira",
            display_name="Jira",
            transport=TransportKind.MCP,
            description="Atlassian Rovo MCP (Jira issues, JQL, comments)",
            placeholder=not bool(
                (settings.atlassian_mcp_token or settings.jira_mcp_token or "").strip()
            ),
        )

    def connect(self) -> None:
        if not settings.connected_system_jira_mcp_enabled and not self._use_seed_fallback:
            raise RuntimeError("CONNECTED_SYSTEM_JIRA_MCP_ENABLED is false")
        self._connected = True

    def health(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNKNOWN
        token = (settings.atlassian_mcp_token or settings.jira_mcp_token or "").strip()
        if token:
            return HealthStatus.HEALTHY
        return HealthStatus.DEGRADED if self._use_seed_fallback else HealthStatus.UNHEALTHY

    def discover_tools(self) -> list[DiscoveredToolDraft]:
        self._catalog_source = CatalogSource.SEED
        return list(JIRA_SEED_TOOLS)

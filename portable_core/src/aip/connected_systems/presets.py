"""MVP connected-system presets (pure data; no SQLModel/persistence)."""

from __future__ import annotations

from typing import Any

from aip.connected_systems.models import TransportKind

BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "github",
        "display_name": "GitHub",
        "provider": "github",
        "mcp_url": "https://api.githubcopilot.com/mcp/",
        "toolsets": "pull_requests,repos,issues,actions",
        "description": "GitHub remote MCP (PRs, repos, issues, Actions)",
        "auth_mode": "github_app",
        "transport": TransportKind.MCP.value,
    },
    {
        "id": "gmail",
        "display_name": "Gmail",
        "provider": "gmail",
        "mcp_url": "",
        "toolsets": "email",
        "description": "Gmail native REST (cataloged like MCP; send/search/reply)",
        "auth_mode": "gmail_oauth",
        "transport": TransportKind.NATIVE.value,
    },
    {
        "id": "calendar",
        "display_name": "Google Calendar",
        "provider": "calendar",
        "mcp_url": "",
        "toolsets": "calendar",
        "description": "Google Calendar native REST (reuses Gmail OAuth; add Calendar scopes)",
        "auth_mode": "gmail_oauth",
        "transport": TransportKind.NATIVE.value,
    },
    {
        "id": "jira",
        "display_name": "Jira",
        "provider": "jira",
        "mcp_url": "https://mcp.atlassian.com/v1/mcp",
        "toolsets": "jira",
        "description": "Atlassian Rovo MCP (Jira issues, JQL, comments)",
        "auth_mode": "bearer",
        "transport": TransportKind.MCP.value,
    },
]

MVP_SYSTEM_IDS = frozenset(p["id"] for p in BUILTIN_PRESETS)


def preset_by_id(system_id: str) -> dict[str, Any] | None:
    for preset in BUILTIN_PRESETS:
        if preset["id"] == system_id:
            return dict(preset)
    return None

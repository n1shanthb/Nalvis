"""Jira ConnectedSystemProvider — Atlassian Rovo remote MCP (+ offline seed)."""

from __future__ import annotations

import asyncio

from aip.config import settings
from aip.connected_systems.models import (
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
    TransportKind,
)

# Offline / demo inventory matching Atlassian Rovo MCP Jira tool names.
JIRA_SEED_TOOLS: list[DiscoveredToolDraft] = [
    DiscoveredToolDraft(
        name="getAccessibleAtlassianResources",
        description="List Atlassian cloud sites (cloudId) accessible to the token",
        input_schema={"type": "object", "properties": {}},
        permissions=["read"],
        toolset="jira",
        capability_tags=["jira_triage"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="getVisibleJiraProjects",
        description="List Jira projects the authenticated user can access",
        input_schema={
            "type": "object",
            "properties": {"cloudId": {"type": "string"}},
            "required": ["cloudId"],
        },
        permissions=["read"],
        toolset="jira",
        capability_tags=["jira_triage"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="getJiraIssue",
        description="Get a Jira issue by ID or key",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "issueIdOrKey": {"type": "string"},
            },
            "required": ["cloudId", "issueIdOrKey"],
        },
        permissions=["read"],
        toolset="jira",
        capability_tags=["jira_triage", "jira_issue"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="searchJiraIssuesUsingJql",
        description="Search Jira issues using JQL",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "jql": {"type": "string"},
                "maxResults": {"type": "integer"},
            },
            "required": ["cloudId", "jql"],
        },
        permissions=["read"],
        toolset="jira",
        capability_tags=["jira_triage", "jira_search"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="createJiraIssue",
        description="Create a Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "projectKey": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "issueTypeName": {"type": "string"},
            },
            "required": ["cloudId", "projectKey", "summary"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_triage", "jira_issue"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="editJiraIssue",
        description="Update fields on an existing Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "issueIdOrKey": {"type": "string"},
                "fields": {"type": "object"},
            },
            "required": ["cloudId", "issueIdOrKey"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_triage", "jira_issue"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="addCommentToJiraIssue",
        description="Add a comment to a Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "issueIdOrKey": {"type": "string"},
                "commentBody": {"type": "string"},
            },
            "required": ["cloudId", "issueIdOrKey", "commentBody"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_triage", "jira_issue"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="transitionJiraIssue",
        description="Perform a workflow transition on a Jira issue",
        input_schema={
            "type": "object",
            "properties": {
                "cloudId": {"type": "string"},
                "issueIdOrKey": {"type": "string"},
                "transitionId": {"type": "string"},
            },
            "required": ["cloudId", "issueIdOrKey", "transitionId"],
        },
        permissions=["write"],
        toolset="jira",
        capability_tags=["jira_triage"],
        department_tags=["engineering"],
    ),
]


def resolve_jira_mcp_token() -> str | None:
    """Raw token from env, then optional registry row."""
    for raw in (settings.atlassian_mcp_token, settings.jira_mcp_token):
        token = (raw or "").strip()
        if token:
            return token
    try:
        from aip.connected_systems.registry import McpServerRow
        from aip.persistence.db import get_session

        with get_session() as session:
            row = session.get(McpServerRow, "jira")
            if row is not None:
                stored = (row.bearer_token or "").strip()
                if stored:
                    return stored
    except Exception:  # noqa: BLE001
        return None
    return None


def jira_mcp_auth_headers() -> dict[str, str]:
    """Personal ATATT tokens use Basic(email:token); service-account keys use Bearer."""
    token = resolve_jira_mcp_token()
    if not token:
        return {}
    email = (settings.atlassian_email or "").strip()
    # Classic personal API tokens start with ATATT and require Basic auth.
    if email and token.startswith("ATATT"):
        import base64

        encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {"Authorization": f"Bearer {token}"}


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Run async discover whether or not a loop is already running (FastAPI)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _mcp_url() -> str:
    return (
        settings.connected_system_jira_mcp_url or "https://mcp.atlassian.com/v1/mcp"
    ).rstrip("/")


class JiraProvider:
    """Atlassian Rovo MCP over Streamable HTTP — Jira tool inventory."""

    def __init__(self, *, use_seed_fallback: bool = True) -> None:
        self._connected = False
        self._use_seed_fallback = use_seed_fallback
        self._last_drafts: list[DiscoveredToolDraft] = []
        self._last_error: str | None = None

    def metadata(self) -> ConnectedSystemMetadata:
        return ConnectedSystemMetadata(
            id="jira",
            provider="jira",
            display_name="Jira",
            transport=TransportKind.MCP_STREAMABLE_HTTP,
            description=(
                "Atlassian Rovo MCP (Jira issues, JQL, comments) — "
                "Bearer service account token"
            ),
            placeholder=not bool(resolve_jira_mcp_token()),
        )

    def connect(self) -> None:
        if not settings.connected_system_jira_mcp_enabled:
            if self._use_seed_fallback:
                self._connected = True
                return
            raise RuntimeError("CONNECTED_SYSTEM_JIRA_MCP_ENABLED is false")
        if resolve_jira_mcp_token():
            self._connected = True
            self._last_error = None
            return
        if self._use_seed_fallback:
            self._connected = True
            return
        raise RuntimeError(
            "Jira MCP token missing — set ATLASSIAN_MCP_TOKEN or paste Bearer on /mcps/jira"
        )

    def disconnect(self) -> None:
        self._connected = False
        self._last_drafts = []

    def health_check(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNKNOWN
        if self._last_error:
            return HealthStatus.UNHEALTHY
        if self._last_drafts:
            return HealthStatus.HEALTHY
        if resolve_jira_mcp_token():
            return HealthStatus.DEGRADED
        return HealthStatus.DEGRADED

    def discover(self) -> list[DiscoveredToolDraft]:
        if not self._connected:
            self.connect()
        if resolve_jira_mcp_token() and settings.connected_system_jira_mcp_enabled:
            try:
                drafts = _run_async(self._discover_live())
                if drafts:
                    self._last_drafts = drafts
                    self._last_error = None
                    return list(drafts)
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)[:400]
                if not self._use_seed_fallback:
                    raise
        drafts = list(JIRA_SEED_TOOLS)
        self._last_drafts = drafts
        return drafts

    async def _discover_live(self) -> list[DiscoveredToolDraft]:
        from agents.mcp import MCPServerStreamableHttp

        headers = jira_mcp_auth_headers()
        if not headers:
            return []
        server = MCPServerStreamableHttp(
            params={"url": _mcp_url() + "/", "headers": headers, "timeout": 45},
            name="jira_mcp",
            client_session_timeout_seconds=45,
        )
        drafts: list[DiscoveredToolDraft] = []
        try:
            await server.connect()
            tools = await server.list_tools()
            for t in tools:
                name = str(getattr(t, "name", "") or "")
                if not name:
                    continue
                desc = str(getattr(t, "description", "") or "")
                schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
                if not isinstance(schema, dict):
                    schema = {"type": "object", "properties": {}}
                drafts.append(
                    DiscoveredToolDraft(
                        name=name,
                        description=desc,
                        input_schema=schema,
                        permissions=["read", "write"],
                        toolset="jira",
                        capability_tags=["jira_triage"],
                        department_tags=["engineering"],
                    )
                )
        finally:
            try:
                await server.cleanup()
            except Exception:  # noqa: BLE001
                pass
        return drafts

"""GitHub remote MCP ConnectedSystemProvider."""

from __future__ import annotations

import asyncio

from aip.config import settings
from aip.connected_systems.models import (
    CatalogSource,
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
    TransportKind,
)


# Deterministic seed used when live MCP is unavailable (tests / offline demo)
GITHUB_SEED_TOOLS: list[DiscoveredToolDraft] = [
    DiscoveredToolDraft(
        name="pull_request_read",
        description="Get pull request details, files, and diff summary",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pullNumber": {"type": "integer"},
            },
            "required": ["owner", "repo", "pullNumber"],
        },
        permissions=["read"],
        toolset="pull_requests",
        capability_tags=["github_pr_review", "review_pull_request"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="pull_request_review_write",
        description="Create a pull request review (approve, comment, or request changes)",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pullNumber": {"type": "integer"},
                "body": {"type": "string"},
                "event": {"type": "string"},
            },
            "required": ["owner", "repo", "pullNumber"],
        },
        permissions=["write"],
        toolset="pull_requests",
        capability_tags=["github_pr_review", "review_pull_request"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="create_pull_request_comment",
        description="Comment on a pull request",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pullNumber": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["owner", "repo", "pullNumber", "body"],
        },
        permissions=["write"],
        toolset="pull_requests",
        capability_tags=["github_pr_review"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="merge_pull_request",
        description="Merge a pull request",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pullNumber": {"type": "integer"},
                "merge_method": {"type": "string"},
            },
            "required": ["owner", "repo", "pullNumber"],
        },
        permissions=["write"],
        toolset="pull_requests",
        capability_tags=["github_pr_review", "merge_pull_request"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="list_pull_requests",
        description="List pull requests for a repository",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
        permissions=["read"],
        toolset="pull_requests",
        capability_tags=["github_pr_review"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="get_file_contents",
        description="Get file contents from a repository",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["owner", "repo", "path"],
        },
        permissions=["read"],
        toolset="repos",
        capability_tags=["code_standards"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="issue_read",
        description="Get GitHub issue details",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "issue_number": {"type": "integer"},
            },
            "required": ["owner", "repo", "issue_number"],
        },
        permissions=["read"],
        toolset="issues",
        capability_tags=["github_issue_resolve"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="issue_write",
        description="Create or update issues and post issue comments",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "issue_number": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
        permissions=["write"],
        toolset="issues",
        capability_tags=["github_issue_resolve"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="list_issues",
        description="List issues in a repository",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
        permissions=["read"],
        toolset="issues",
        capability_tags=["github_issue_resolve"],
        department_tags=["engineering"],
    ),
    DiscoveredToolDraft(
        name="search_issues",
        description="Search issues and pull requests",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
        permissions=["read"],
        toolset="issues",
        capability_tags=["github_issue_resolve"],
        department_tags=["engineering"],
    ),
]


def _toolsets() -> list[str]:
    raw = (settings.connected_system_github_mcp_toolsets or "pull_requests,repos,issues,actions").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


def _mcp_url() -> str:
    return (
        settings.connected_system_github_mcp_url
        or "https://api.githubcopilot.com/mcp/"
    ).rstrip("/") + "/"


def _auth_headers() -> dict[str, str]:
    from aip.integrations.github_app import resolve_github_token

    token = resolve_github_token()
    if not token:
        raise RuntimeError(
            "GitHub auth missing — set GitHub App credentials or GITHUB_TOKEN"
        )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-MCP-Toolsets": ",".join(_toolsets()),
    }
    return headers


class GitHubProvider:
    """First ConnectedSystemProvider — GitHub remote MCP over Streamable HTTP."""

    def __init__(self, *, use_seed_fallback: bool = False) -> None:
        self._connected = False
        self._use_seed_fallback = use_seed_fallback
        self._last_drafts: list[DiscoveredToolDraft] = []
        self._last_error: str | None = None
        self._catalog_source = CatalogSource.UNAVAILABLE

    def catalog_source(self) -> CatalogSource:
        return self._catalog_source

    def metadata(self) -> ConnectedSystemMetadata:
        return ConnectedSystemMetadata(
            id="github",
            provider="github",
            display_name="GitHub MCP",
            transport=TransportKind.MCP_STREAMABLE_HTTP,
            description="GitHub remote MCP (pull requests, repos)",
        )

    def connect(self) -> None:
        if not settings.connected_system_github_mcp_enabled:
            # Still allow seed/demo connect when disabled for live MCP
            if self._use_seed_fallback:
                self._connected = True
                return
            raise RuntimeError("CONNECTED_SYSTEM_GITHUB_MCP_ENABLED is false")
        # Auth probe
        try:
            _auth_headers()
        except RuntimeError:
            if self._use_seed_fallback:
                self._connected = True
                return
            raise
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False
        self._last_drafts = []

    def health_check(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNKNOWN
        if self._last_drafts:
            return HealthStatus.HEALTHY
        return HealthStatus.DEGRADED if self._use_seed_fallback else HealthStatus.HEALTHY

    def discover(self) -> list[DiscoveredToolDraft]:
        if not self._connected:
            self.connect()
        drafts = self._discover_live()
        if drafts:
            self._last_drafts = drafts
            self._catalog_source = CatalogSource.LIVE
            return drafts
        if self._use_seed_fallback:
            self._last_drafts = list(GITHUB_SEED_TOOLS)
            self._catalog_source = CatalogSource.SEED
            return list(GITHUB_SEED_TOOLS)
        self._catalog_source = CatalogSource.UNAVAILABLE
        return []

    def _discover_live(self) -> list[DiscoveredToolDraft]:
        if not settings.connected_system_github_mcp_enabled:
            return []
        try:
            _auth_headers()
        except RuntimeError:
            return []
        try:
            return asyncio.run(self._list_tools_async())
        except Exception as exc:  # noqa: BLE001
            # Keep failure visible for operators; seed path may still apply.
            self._last_error = str(exc)
            return []

    async def _list_tools_async(self) -> list[DiscoveredToolDraft]:
        from agents.mcp import MCPServerStreamableHttp

        headers = _auth_headers()
        server = MCPServerStreamableHttp(
            params={"url": _mcp_url(), "headers": headers, "timeout": 30},
            name="github_mcp",
            client_session_timeout_seconds=30,
        )
        drafts: list[DiscoveredToolDraft] = []
        async with server:
            tools = await server.list_tools()
            for t in tools or []:
                name = getattr(t, "name", None) or ""
                if not name:
                    continue
                schema = getattr(t, "inputSchema", None) or getattr(
                    t, "input_schema", None
                ) or {"type": "object", "properties": {}}
                desc = getattr(t, "description", None) or ""
                drafts.append(
                    DiscoveredToolDraft(
                        name=str(name),
                        description=str(desc),
                        input_schema=dict(schema) if isinstance(schema, dict) else {},
                        permissions=["read", "write"],
                        toolset=_guess_toolset(str(name)),
                        capability_tags=_guess_caps(str(name)),
                        department_tags=["engineering"],
                    )
                )
        return drafts


def _guess_toolset(name: str) -> str:
    n = name.lower()
    if "issue" in n:
        return "issues"
    if "pull" in n or "pr_" in n or "review" in n or "merge" in n:
        return "pull_requests"
    if "repo" in n or "file" in n or "content" in n or "branch" in n or "commit" in n:
        return "repos"
    return "general"


def _guess_caps(name: str) -> list[str]:
    n = name.lower()
    tags: list[str] = []
    if "issue" in n:
        tags.append("github_issue_resolve")
    else:
        tags.append("github_pr_review")
    if "review" in n:
        tags.append("review_pull_request")
    if "merge" in n:
        tags.append("merge_pull_request")
    return tags

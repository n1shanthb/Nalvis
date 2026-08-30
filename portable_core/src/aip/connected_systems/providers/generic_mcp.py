"""Generic Streamable HTTP MCP provider (no DB registry dependency)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aip.config import settings
from aip.connected_systems.models import (
    CatalogSource,
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
    TransportKind,
)


@dataclass
class McpEndpointConfig:
    """Portable stand-in for the legacy McpServerRow."""

    id: str
    display_name: str
    provider: str = "generic"
    mcp_url: str = ""
    toolsets: str = ""
    description: str = ""
    auth_mode: str = "bearer"
    bearer_token: str = ""
    status: str = "disconnected"
    last_error: str | None = None
    extra: dict = field(default_factory=dict)


class GenericMcpProvider:
    """Connect / discover against an arbitrary MCP Streamable HTTP endpoint."""

    def __init__(
        self,
        row: McpEndpointConfig,
        *,
        use_seed_fallback: bool | None = None,
    ) -> None:
        self._row = row
        self._connected = row.status == "connected"
        self._last_drafts: list[DiscoveredToolDraft] = []
        self._last_error: str | None = row.last_error
        self._use_seed_fallback = (
            settings.offline_demo_mode if use_seed_fallback is None else use_seed_fallback
        )
        self._catalog_source = CatalogSource.UNAVAILABLE

    def catalog_source(self) -> CatalogSource:
        return self._catalog_source

    def metadata(self) -> ConnectedSystemMetadata:
        url = (self._row.mcp_url or "").strip()
        return ConnectedSystemMetadata(
            id=self._row.id,
            provider=self._row.provider,
            display_name=self._row.display_name,
            transport=TransportKind.MCP,
            description=self._row.description or url,
            placeholder=not bool(url),
        )

    def connect(self) -> None:
        url = (self._row.mcp_url or "").strip()
        if not url and not self._use_seed_fallback:
            raise RuntimeError("mcp_url is empty")
        self._connected = True
        self._row.status = "connected"

    def health(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNKNOWN
        if (self._row.mcp_url or "").strip():
            return HealthStatus.HEALTHY
        return HealthStatus.DEGRADED if self._use_seed_fallback else HealthStatus.UNHEALTHY

    def discover_tools(self) -> list[DiscoveredToolDraft]:
        if not self._connected:
            self.connect()
        drafts = self._discover_live()
        if drafts:
            self._catalog_source = CatalogSource.LIVE
            self._last_drafts = drafts
            return drafts
        if self._use_seed_fallback:
            self._catalog_source = CatalogSource.SEED
            self._last_drafts = []
            return []
        self._catalog_source = CatalogSource.UNAVAILABLE
        return []

    def _discover_live(self) -> list[DiscoveredToolDraft]:
        url = (self._row.mcp_url or "").strip()
        if not url:
            return []
        try:
            return asyncio.run(self._list_tools_async(url))
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            return []

    async def _list_tools_async(self, url: str) -> list[DiscoveredToolDraft]:
        from agents.mcp import MCPServerStreamableHttp

        headers: dict[str, str] = {}
        token = (self._row.bearer_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        server = MCPServerStreamableHttp(
            params={"url": url, "headers": headers, "timeout": 30},
            name=f"mcp_{self._row.id}",
            client_session_timeout_seconds=30,
        )
        drafts: list[DiscoveredToolDraft] = []
        async with server:
            tools = await server.list_tools()
            for t in tools or []:
                name = getattr(t, "name", None) or ""
                if not name:
                    continue
                schema = (
                    getattr(t, "inputSchema", None)
                    or getattr(t, "input_schema", None)
                    or {"type": "object", "properties": {}}
                )
                desc = getattr(t, "description", None) or ""
                drafts.append(
                    DiscoveredToolDraft(
                        name=str(name),
                        description=str(desc),
                        input_schema=dict(schema) if isinstance(schema, dict) else {},
                        permissions=["read", "write"],
                        toolset=self._row.toolsets.split(",")[0].strip() if self._row.toolsets else "general",
                        capability_tags=[],
                        department_tags=[],
                    )
                )
        return drafts

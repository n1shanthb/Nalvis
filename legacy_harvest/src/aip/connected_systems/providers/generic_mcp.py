"""Generic Streamable HTTP MCP provider — works for any registered MCP URL."""

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
from aip.connected_systems.registry import McpServerRow


class GenericMcpProvider:
    """Connect / discover against an arbitrary MCP Streamable HTTP endpoint."""

    def __init__(self, row: McpServerRow, *, use_seed_fallback: bool | None = None) -> None:
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
            transport=TransportKind.MCP_STREAMABLE_HTTP,
            description=self._row.description,
            placeholder=not bool(url) and self._row.id != "github",
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        token = (self._row.bearer_token or "").strip()
        if self._row.auth_mode == "github_app" or self._row.id == "github":
            from aip.integrations.github_app import resolve_github_token

            token = resolve_github_token() or token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        toolsets = (self._row.toolsets or "").strip()
        if toolsets:
            headers["X-MCP-Toolsets"] = toolsets
        return headers

    def connect(self) -> None:
        url = (self._row.mcp_url or "").strip()
        if not url and self._row.id != "github":
            raise RuntimeError(
                f"{self._row.display_name}: set an MCP URL before connecting"
            )
        if self._row.auth_mode in {"bearer", "github_app"} or self._row.id == "github":
            # Probe auth when required
            if self._row.id == "github" or self._row.auth_mode == "github_app":
                from aip.integrations.github_app import resolve_github_token

                if not resolve_github_token() and not (self._row.bearer_token or "").strip():
                    if self._row.id == "github" and self._use_seed_fallback:
                        self._connected = True
                        self._last_error = None
                        self._catalog_source = CatalogSource.SEED
                        return
                    raise RuntimeError("GitHub auth missing (App or token)")
            elif self._row.auth_mode == "bearer" and not (self._row.bearer_token or "").strip():
                # URL-only MCPs that don't need auth are allowed with auth_mode=none
                pass
        self._connected = True
        self._last_error = None

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
        url = (self._row.mcp_url or "").strip()
        if not url and self._row.id != "github":
            return HealthStatus.DEGRADED
        return HealthStatus.DEGRADED

    def discover(self) -> list[DiscoveredToolDraft]:
        if not self._connected:
            self.connect()
        # GitHub seed fallback when live fails
        if self._row.id == "github":
            drafts = self._discover_live()
            if drafts:
                self._last_drafts = drafts
                self._catalog_source = CatalogSource.LIVE
                return drafts
            if self._use_seed_fallback:
                from aip.connected_systems.providers.github import GITHUB_SEED_TOOLS

                self._last_drafts = list(GITHUB_SEED_TOOLS)
                self._catalog_source = CatalogSource.SEED
                return list(GITHUB_SEED_TOOLS)
            self._catalog_source = CatalogSource.UNAVAILABLE
            self._last_drafts = []
            return []

        url = (self._row.mcp_url or "").strip()
        if not url:
            raise RuntimeError(f"{self._row.display_name}: MCP URL required for discovery")
        drafts = self._discover_live()
        self._last_drafts = drafts
        return drafts

    def _discover_live(self) -> list[DiscoveredToolDraft]:
        url = (self._row.mcp_url or "").strip()
        if not url:
            return []
        try:
            return asyncio.run(self._list_tools_async(url))
        except RuntimeError:
            # Already in an event loop — run in a fresh thread loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(self._list_tools_async(url))).result()
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            return []

    async def _list_tools_async(self, url: str) -> list[DiscoveredToolDraft]:
        from agents.mcp import MCPServerStreamableHttp

        headers = self._headers()
        server = MCPServerStreamableHttp(
            params={
                "url": url.rstrip("/") + "/",
                "headers": headers,
                "timeout": 30,
            },
            name=f"{self._row.id}_mcp",
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
                drafts.append(
                    DiscoveredToolDraft(
                        name=str(name),
                        description=str(getattr(t, "description", "") or ""),
                        input_schema=dict(schema) if isinstance(schema, dict) else {},
                        permissions=["read", "write"],
                        toolset=self._row.toolsets.split(",")[0].strip()
                        if self._row.toolsets
                        else "general",
                        capability_tags=[self._row.id],
                        department_tags=[],
                    )
                )
        self._last_error = None
        return drafts

"""Google Calendar ConnectedSystemProvider — native REST tools cataloged like MCP."""

from __future__ import annotations

from aip.config import settings
from aip.connected_systems.models import (
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
    TransportKind,
)
from aip.tools.calendar import build_calendar_tools, calendar_configured


def calendar_seed_drafts() -> list[DiscoveredToolDraft]:
    drafts: list[DiscoveredToolDraft] = []
    write_names = {"create_event", "update_event", "delete_event"}
    for tool, tags, _requires in build_calendar_tools():
        drafts.append(
            DiscoveredToolDraft(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.input_schema or {}),
                permissions=["write"] if tool.name in write_names else ["read"],
                toolset="calendar",
                capability_tags=sorted(set(tags + ["calendar_assist"])),
                department_tags=["operations", "communications"],
            )
        )
    return drafts


class CalendarProvider:
    """Native transport Connected System — inventory via seed drafts, execute via ToolRegistry."""

    def __init__(self, *, use_seed_fallback: bool = True) -> None:
        self._connected = False
        self._use_seed_fallback = use_seed_fallback
        self._last_drafts: list[DiscoveredToolDraft] = []

    def metadata(self) -> ConnectedSystemMetadata:
        return ConnectedSystemMetadata(
            id="calendar",
            provider="calendar",
            display_name="Google Calendar",
            transport=TransportKind.NATIVE,
            description=(
                "Google Calendar native REST (reuses Gmail OAuth; add Calendar scopes)"
            ),
            placeholder=not calendar_configured(),
        )

    def connect(self) -> None:
        if not settings.connected_system_calendar_enabled:
            if self._use_seed_fallback:
                self._connected = True
                return
            raise RuntimeError("CONNECTED_SYSTEM_CALENDAR_ENABLED is false")
        if calendar_configured():
            self._connected = True
            return
        if self._use_seed_fallback:
            self._connected = True
            return
        raise RuntimeError(
            "Google OAuth not configured — set GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN/USER "
            "and include Calendar scopes on the refresh token"
        )

    def disconnect(self) -> None:
        self._connected = False
        self._last_drafts = []

    def health_check(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNKNOWN
        if calendar_configured():
            return HealthStatus.HEALTHY
        return HealthStatus.DEGRADED

    def discover(self) -> list[DiscoveredToolDraft]:
        if not self._connected:
            self.connect()
        drafts = calendar_seed_drafts()
        self._last_drafts = drafts
        return list(drafts)

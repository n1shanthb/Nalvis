"""Provider protocol (lightweight; no registry DB)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aip.connected_systems.models import (
    ConnectedSystemMetadata,
    DiscoveredToolDraft,
    HealthStatus,
)


@runtime_checkable
class ConnectedSystemProvider(Protocol):
    def metadata(self) -> ConnectedSystemMetadata: ...

    def connect(self) -> None: ...

    def health(self) -> HealthStatus: ...

    def discover_tools(self) -> list[DiscoveredToolDraft]: ...

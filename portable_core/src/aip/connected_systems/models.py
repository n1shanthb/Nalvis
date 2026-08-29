"""Connected-system model contracts (recreated; missing from harvest)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransportKind(str, Enum):
    MCP = "mcp"
    NATIVE = "native"


class ConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class HealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CatalogSource(str, Enum):
    LIVE = "live"
    SEED = "seed"
    UNAVAILABLE = "unavailable"


class ConnectedSystemMetadata(BaseModel):
    id: str
    provider: str
    display_name: str
    transport: TransportKind = TransportKind.MCP
    description: str = ""
    placeholder: bool = False


class DiscoveredToolDraft(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    permissions: list[str] = Field(default_factory=list)
    toolset: str = ""
    capability_tags: list[str] = Field(default_factory=list)
    department_tags: list[str] = Field(default_factory=list)

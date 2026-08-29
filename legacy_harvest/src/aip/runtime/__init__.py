"""Runtime package — OpenAI Agents SDK adapter + MCP attach + resolution types."""

from aip.runtime.adapters.openai import (
    OpenAIAgentsRuntimeAdapter,
    build_mcp_servers,
)
from aip.runtime.resolution import ResolvedTransportAttachment, ToolResolution

__all__ = [
    "OpenAIAgentsRuntimeAdapter",
    "ResolvedTransportAttachment",
    "ToolResolution",
    "build_mcp_servers",
]
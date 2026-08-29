"""Native ToolRegistry — portable name → Tool.execute (Gmail REST, etc.)."""

from __future__ import annotations

from aip.contracts.tools import Tool
from aip.tools.base import NativeTool
from aip.tools.calendar import build_calendar_tools, calendar_configured
from aip.tools.gmail import build_gmail_tools, gmail_configured


class ToolRegistry:
    """In-process registry of native Python tools."""

    def __init__(self) -> None:
        self._tools: dict[str, NativeTool] = {}
        self.reload()

    def reload(self) -> None:
        self._tools.clear()
        for tool, _tags, requires_gmail in build_gmail_tools():
            if requires_gmail and not gmail_configured():
                # Still register so Specs resolve; execute returns config error.
                pass
            self._tools[tool.name] = tool
        for tool, _tags, requires_oauth in build_calendar_tools():
            if requires_oauth and not calendar_configured():
                pass
            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def resolve(self, names: list[str]) -> list[Tool]:
        out: list[Tool] = []
        for name in names:
            tool = self._tools.get(name)
            if tool is not None:
                out.append(tool)
        return out

    def names(self) -> list[str]:
        return sorted(self._tools)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry

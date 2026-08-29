"""NativeTool adapter for Tool protocol (portable; no orchestration)."""

from __future__ import annotations

from typing import Any, Callable


class NativeTool:
    """Simple callable tool that satisfies aip.contracts.tools.Tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        fn: Callable[[dict[str, Any]], dict[str, Any]],
        output_schema: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}
        self.output_schema = output_schema or {"type": "object"}
        self._fn = fn

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        return self._fn(input or {})

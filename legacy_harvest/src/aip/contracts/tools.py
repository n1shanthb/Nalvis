from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def execute(self, input: dict[str, Any]) -> dict[str, Any]: ...

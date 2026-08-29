from typing import Any, Protocol, runtime_checkable

from aip.contracts.llm import LLMClient
from aip.contracts.models import (
    AgentSpecification,
    ExecutionInput,
    ExecutionResult,
    ExecutionState,
)
from aip.contracts.tools import Tool


@runtime_checkable
class ExecutableAgent(Protocol):
    def invoke(
        self, input: ExecutionInput, state: ExecutionState
    ) -> ExecutionResult: ...


@runtime_checkable
class RuntimeAdapter(Protocol):
    def adapt(
        self,
        spec: AgentSpecification,
        tools: list[Tool],
        llm: LLMClient,
        *,
        tool_resolution: Any | None = None,
    ) -> ExecutableAgent: ...

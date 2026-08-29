from typing import Protocol, runtime_checkable

from aip.contracts.models import LLMRequest, LLMResponse


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...

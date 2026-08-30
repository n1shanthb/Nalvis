"""Policy Request and Decision contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from aip.guardrails.models import GuardrailEffect


from aip.guardrails.identity import AgentExecutionIdentity

class PolicyRequest(BaseModel):
    identity: AgentExecutionIdentity
    tool: str
    arguments: dict[str, Any]
    context: dict[str, Any] = {}


class PolicyDecision(BaseModel):
    decision: GuardrailEffect
    guardrail_id: str | None = None
    reason: str

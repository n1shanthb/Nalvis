"""Stable policy / guardrail interfaces for the clean rebuild."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from aip.guardrails.decisions import PolicyDecision, PolicyRequest
from aip.guardrails.engine import GuardrailEngine
from aip.guardrails.models import Guardrail, GuardrailEffect


@runtime_checkable
class GuardrailDecisionEngine(Protocol):
    def evaluate(self, request: PolicyRequest) -> PolicyDecision: ...


def build_engine(rules: list[Guardrail]) -> GuardrailEngine:
    return GuardrailEngine(rules)


__all__ = [
    "Guardrail",
    "GuardrailDecisionEngine",
    "GuardrailEffect",
    "GuardrailEngine",
    "PolicyDecision",
    "PolicyRequest",
    "build_engine",
]

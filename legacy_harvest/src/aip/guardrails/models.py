"""Guardrail data contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class GuardrailEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"

class PolicyScope(str, Enum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    PROJECT = "project"
    TEAM = "team"
    AGENT = "agent"


class PolicyCondition(BaseModel):
    match_context: dict[str, str] | None = None
    match_arguments: dict[str, str] | None = None
    match_arguments_in: dict[str, list[str]] | None = None

class Guardrail(BaseModel):
    id: str
    action: str
    effect: GuardrailEffect
    conditions: PolicyCondition | None = None
    policy_scope: PolicyScope | None = None
    label: str | None = None
    reason: str | None = None

"""Shared domain models for AgentSuite v2 foundations.

Tier A keeps graph, LLM, and execution shapes needed by contracts/runtime.
Workforce / recommendation / analysis models intentionally omitted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Entity(BaseModel):
    id: str
    type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    source: str = "fixture"
    confidence: float | None = None


class Relationship(BaseModel):
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None


class Ontology(BaseModel):
    entity_types: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)
    synonyms: dict[str, list[str]] = Field(default_factory=dict)


class EnterpriseKnowledgeGraph(BaseModel):
    """Layer 0 canonical graph — the only graph shape every higher layer sees.

    Immutable and source-independent: a YAML fixture and the Enterprise
    Knowledge Graph API both normalize into this exact shape.
    """

    org_id: str
    version: str
    entities: list[Entity]
    relationships: list[Relationship]
    ontology: Ontology
    metadata: dict[str, Any] = Field(default_factory=dict)


# Compatibility alias — pre-Layer-0 code still imports KnowledgeGraphSnapshot.
KnowledgeGraphSnapshot = EnterpriseKnowledgeGraph


class EnterpriseContext(BaseModel):
    """Layer 0 boundary object: the canonical graph plus provider provenance.

    Higher layers consume `graph`. The `provider_*` fields exist only so
    Layer 0 can debug what a provider returned; no later layer should branch
    on them.
    """

    org_id: str
    version: str
    source: str
    graph: EnterpriseKnowledgeGraph
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    provider_version: str | None = None
    provider_payload: dict[str, Any] | None = None


# AgentSpecification lives in specification.py — re-exported for contract convenience.
from aip.contracts.specification import (  # noqa: E402
    AgentIdentity,
    AgentSpecification,
    ExecutionConfig,
    KnowledgeRef,
    MemoryConfig,
    PromptConfig,
    RuntimeConfig,
    TriggerConfig,
)


class LLMRequest(BaseModel):
    messages: list[dict[str, Any]]
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ExecutionInput(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class ToolEvent(BaseModel):
    name: str
    input: dict[str, Any]
    output: dict[str, Any]


class ExecutionState(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    output: str
    tool_events: list[ToolEvent] = Field(default_factory=list)
    state_summary: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


class TriggerType(str, Enum):
    manual = "manual"
    api = "api"
    webhook = "webhook"
    schedule = "schedule"

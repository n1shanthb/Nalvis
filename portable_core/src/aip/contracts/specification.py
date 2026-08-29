"""Typed AgentSpecification contract (schema v1) and nested configs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from aip.contracts.spec_version import (
    DEFAULT_ADAPTER,
    DEFAULT_RUNTIME_PROFILE,
    SPEC_SCHEMA_VERSION,
)
from aip.guardrails.models import Guardrail


class AgentIdentity(BaseModel):
    id: str
    title: str
    org_id: str
    version: str | None = None  # display / template semver only


class PromptConfig(BaseModel):
    system: str
    style: str | None = None
    prompt_version: str | None = None


class KnowledgeRef(BaseModel):
    id: str | None = None
    type: str | None = None
    ref: str | None = None
    scope: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryConfig(BaseModel):
    short_term: bool = True
    long_term: bool = False


class TriggerConfig(BaseModel):
    type: str = "manual"
    webhook_ids: list[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    """Portable runtime selector — no framework objects."""

    adapter: str = DEFAULT_ADAPTER
    profile: str = DEFAULT_RUNTIME_PROFILE
    config: dict[str, Any] = Field(default_factory=dict)


class ExecutionConfig(BaseModel):
    mode: str = "synchronous"
    max_steps: int = 12


class AgentSpecification(BaseModel):
    """Canonical runtime-independent agent artifact (schema v1)."""

    spec_schema_version: str = SPEC_SCHEMA_VERSION
    spec_version: int = 1
    agent: AgentIdentity
    goal: str
    prompt: PromptConfig
    capability_ids: list[str] = Field(default_factory=list)
    knowledge: list[KnowledgeRef | dict[str, Any]] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: list[str] = Field(default_factory=list)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    permissions: list[str] = Field(default_factory=list)
    guardrails: list[str | Guardrail] = Field(default_factory=list)
    evaluation: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        from aip.contracts.spec_validation import migrate_spec_dict

        return migrate_spec_dict(data)

    @field_validator("spec_version")
    @classmethod
    def _spec_version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("spec_version must be >= 1")
        return v

    @property
    def spec_id(self) -> str:
        return self.agent.id

    @property
    def version(self) -> str:
        return self.agent.version or str(self.spec_version)

    @property
    def adapter_name(self) -> str:
        return self.runtime.adapter

    def runtime_setting(self, key: str, default: Any = None) -> Any:
        return self.runtime.config.get(key, default)

    def prompt_system(self) -> str:
        return self.prompt.system

    def resolved_prompt_version(self) -> str:
        if self.prompt.prompt_version:
            return self.prompt.prompt_version
        return f"sys-{hash(self.prompt.system) & 0xFFFFFFFF:08x}"

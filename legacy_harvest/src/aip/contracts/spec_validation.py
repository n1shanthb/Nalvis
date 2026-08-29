"""Validate and migrate AgentSpecification payloads."""

from __future__ import annotations

from typing import Any

from aip.contracts.spec_version import (
    DEFAULT_ADAPTER,
    DEFAULT_RUNTIME_PROFILE,
    SPEC_SCHEMA_VERSION,
)


_FORBIDDEN_TOP_LEVEL = frozenset(
    {
        "langgraph",
        "crewai",
        "openai_agents",
        "autogen",
        "azure_foundry",
        "mcp_session",
    }
)


def migrate_spec_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy Spec dicts to schema v1 shape (in-memory)."""
    out = dict(data)

    out.setdefault("spec_schema_version", SPEC_SCHEMA_VERSION)
    if "spec_version" not in out:
        out["spec_version"] = 1

    agent = out.get("agent")
    if isinstance(agent, dict) and "id" in agent:
        out["agent"] = {
            "id": str(agent["id"]),
            "title": str(agent.get("title") or agent["id"]),
            "org_id": str(agent.get("org_id") or ""),
            "version": agent.get("version"),
        }

    caps = out.get("capability_ids")
    if not caps:
        meta = out.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("capability_ids"):
            out["capability_ids"] = list(meta["capability_ids"])
        else:
            out.setdefault("capability_ids", [])

    prompt = out.get("prompt")
    if isinstance(prompt, dict):
        system = prompt.get("system") or ""
        out["prompt"] = {
            "system": str(system),
            "style": prompt.get("style"),
            "prompt_version": prompt.get("prompt_version"),
        }
    elif isinstance(prompt, str):
        out["prompt"] = {"system": prompt}

    memory = out.get("memory")
    if isinstance(memory, dict):
        out["memory"] = {
            "short_term": bool(memory.get("short_term", True)),
            "long_term": bool(memory.get("long_term", False)),
        }
    elif memory is None:
        out["memory"] = {"short_term": True, "long_term": False}

    trigger = out.get("trigger")
    if hasattr(trigger, "model_dump"):
        trigger = trigger.model_dump()
    webhook_ids: list[str] = []
    trigger_type = "manual"
    if isinstance(trigger, dict):
        trigger_type = str(trigger.get("type") or "manual")
        raw_ids = trigger.get("webhook_ids") or []
        if isinstance(raw_ids, list):
            webhook_ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    elif isinstance(trigger, str):
        trigger_type = trigger
    meta_preview = out.get("metadata")
    if not webhook_ids and isinstance(meta_preview, dict):
        legacy = meta_preview.get("webhooks") or []
        if isinstance(legacy, list):
            webhook_ids = [str(item).strip() for item in legacy if str(item).strip()]
    out["trigger"] = {"type": trigger_type, "webhook_ids": webhook_ids}

    runtime = out.get("runtime")
    if hasattr(runtime, "model_dump"):
        runtime = runtime.model_dump()
    if not isinstance(runtime, dict):
        runtime = {}
    if "config" in runtime and isinstance(runtime["config"], dict):
        config = dict(runtime["config"])
        adapter = str(runtime.get("adapter") or DEFAULT_ADAPTER)
        profile = str(runtime.get("profile") or DEFAULT_RUNTIME_PROFILE)
    else:
        config = {}
        for key in ("model", "temperature", "max_tool_rounds"):
            if key in runtime:
                config[key] = runtime[key]
        adapter = str(runtime.get("adapter") or DEFAULT_ADAPTER)
        profile = str(runtime.get("profile") or DEFAULT_RUNTIME_PROFILE)
    out["runtime"] = {"adapter": adapter, "profile": profile, "config": config}

    execution = out.get("execution")
    if hasattr(execution, "model_dump"):
        execution = execution.model_dump()
    if isinstance(execution, dict):
        out["execution"] = {
            "mode": str(execution.get("mode") or "synchronous"),
            "max_steps": int(execution.get("max_steps") or 12),
        }
    else:
        out["execution"] = {"mode": "synchronous", "max_steps": 12}

    knowledge = out.get("knowledge") or []
    normalized_k: list[Any] = []
    for item in knowledge:
        if isinstance(item, dict):
            normalized_k.append(item)
        else:
            normalized_k.append({"id": str(item), "ref": str(item)})
    out["knowledge"] = normalized_k

    out.setdefault("tools", [])
    out.setdefault("permissions", [])
    out.setdefault("guardrails", [])
    out.setdefault("evaluation", {})
    out.setdefault("outputs", {})
    out.setdefault("metadata", {})
    return out


def validate_agent_specification(spec: Any) -> None:
    """Raise ValueError if Spec violates portable-contract invariants."""
    from aip.contracts.specification import AgentSpecification

    if not isinstance(spec, AgentSpecification):
        spec = AgentSpecification.model_validate(spec)

    if spec.spec_schema_version != SPEC_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported spec_schema_version {spec.spec_schema_version!r}; "
            f"expected {SPEC_SCHEMA_VERSION!r}"
        )
    if not spec.agent.id:
        raise ValueError("agent.id is required")
    if not spec.prompt.system:
        raise ValueError("prompt.system is required")
    if not spec.runtime.adapter:
        raise ValueError("runtime.adapter is required")
    meta_keys = set((spec.metadata or {}).keys())
    bad = meta_keys & _FORBIDDEN_TOP_LEVEL
    if bad:
        raise ValueError(f"Forbidden runtime-specific metadata keys: {sorted(bad)}")
    for key in _FORBIDDEN_TOP_LEVEL:
        if key in spec.runtime.config:
            raise ValueError(f"Forbidden runtime.config key: {key}")

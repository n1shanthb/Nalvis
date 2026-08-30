"""Unified LLM client — OPENAI_API_KEY | OPENROUTER_API_KEY + LLM_API_BASE.

Never hardcodes a vendor; OpenAI SDK with optional base_url is fine.
Empty OPENAI_API_KEY with a set OpenRouter key still enables LLM paths.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


def _settings_llm():
    """Lazy import — avoid circular imports with aip.config."""
    from aip.config import settings

    return settings


def resolve_llm_api_key() -> str:
    """Prefer env OPENAI_API_KEY / OPENROUTER_API_KEY; else settings from .env."""
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if openai_key:
        return openai_key
    openrouter_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if openrouter_key:
        return openrouter_key
    s = _settings_llm()
    openai_key = (s.openai_api_key or "").strip()
    if openai_key:
        return openai_key
    return (s.openrouter_api_key or "").strip()


def resolve_llm_base_url() -> str | None:
    base = (os.environ.get("LLM_API_BASE") or "").strip()
    if not base:
        base = (_settings_llm().llm_api_base or "").strip()
    if base:
        return base.rstrip("/")
    # OpenRouter key without explicit base → use OpenRouter endpoint
    if resolve_llm_api_key() and not (
        (os.environ.get("OPENAI_API_KEY") or "").strip()
        or (_settings_llm().openai_api_key or "").strip()
    ):
        return "https://openrouter.ai/api/v1"
    return None


def resolve_llm_model() -> str:
    s = _settings_llm()
    return (
        (os.environ.get("LLM_MODEL") or "").strip()
        or (os.environ.get("OPENAI_MODEL") or "").strip()
        or (s.llm_model or "").strip()
        or (s.openai_model or "").strip()
        or "gpt-4.1-mini"
    )


def llm_configured() -> bool:
    return bool(resolve_llm_api_key())


@lru_cache(maxsize=1)
def get_llm_client():
    """Cached OpenAI client configured for the active key + base URL."""
    from openai import OpenAI

    api_key = resolve_llm_api_key()
    if not api_key:
        raise RuntimeError("No LLM API key (OPENAI_API_KEY or OPENROUTER_API_KEY)")
    kwargs: dict[str, Any] = {"api_key": api_key}
    base = resolve_llm_base_url()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs)


def _strip_json_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def chat_completion_text(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    model: str | None = None,
) -> str:
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=model or resolve_llm_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def chat_completion_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    model: str | None = None,
) -> Any:
    text = chat_completion_text(
        system=system or "You output only valid JSON.",
        user=user,
        temperature=temperature,
        model=model,
    )
    return json.loads(_strip_json_fences(text))


def reset_llm_client_cache() -> None:
    """Test helper — clear cached client after env changes."""
    get_llm_client.cache_clear()

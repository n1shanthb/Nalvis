"""Unified OpenAI-compatible LLM client (OpenAI or OpenRouter)."""

from aip.llm.client import (
    chat_completion_json,
    chat_completion_text,
    get_llm_client,
    llm_configured,
    resolve_llm_api_key,
    resolve_llm_base_url,
    resolve_llm_model,
)

__all__ = [
    "chat_completion_json",
    "chat_completion_text",
    "get_llm_client",
    "llm_configured",
    "resolve_llm_api_key",
    "resolve_llm_base_url",
    "resolve_llm_model",
]

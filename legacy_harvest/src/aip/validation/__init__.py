"""Post-execution validation — claim verification, response SLA, guardrail bypass."""

from __future__ import annotations

from typing import Any

__all__ = ["validate_after_run", "validate_execution_id", "revalidate_execution"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from aip.validation import engine as validation_engine

        return getattr(validation_engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

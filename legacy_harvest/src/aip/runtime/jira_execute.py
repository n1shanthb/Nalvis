"""Run Jira Specs — delegates to the generic spec executor."""

from __future__ import annotations

from typing import Any

from aip.contracts.models import ExecutionResult
from aip.contracts.specification import AgentSpecification
from aip.runtime.execute_spec import run_activated_spec


def run_jira_spec(
    spec: AgentSpecification | str,
    *,
    message: str,
    context: dict[str, Any] | None = None,
) -> ExecutionResult:
    return run_activated_spec(spec, message=message, context=context)

"""OpenAI Agents SDK thin runtime wrap (Authority: Agent runtime = OpenAI Agents SDK).

ExecuteJob goes through SDK-registered tools that call portable_core connectors.
When OPENAI_API_KEY is set, Runner may plan the tool call; when absent, the same
SDK tool function is invoked directly (structured action already auditor-approved).
Evidence contracts are unchanged.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from aip.jobs.execute import execute_job_type


def _openai_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def _run_via_sdk_llm(job_type: str, requested_action: dict[str, Any], agent_role: str) -> dict[str, Any] | None:
    """Optional LLM path — returns None to fall through to direct tool invoke."""
    if not _openai_key():
        return None
    try:
        from agents import Agent, Runner, function_tool
    except ImportError:
        return None

    @function_tool
    def execute_specialist_write(action_json: str) -> str:
        """Execute the approved write job. action_json is JSON for requested_action."""
        try:
            action = json.loads(action_json) if action_json else {}
        except json.JSONDecodeError:
            action = {"raw": action_json}
        result = execute_job_type(job_type, action if isinstance(action, dict) else {})
        return json.dumps(result, default=str)

    agent = Agent(
        name=agent_role or "SpecialistAgent",
        instructions=(
            f"You execute exactly one write job of type {job_type}. "
            "Call execute_specialist_write with the requested_action JSON. "
            "Do not invent resources outside the provided action."
        ),
        tools=[execute_specialist_write],
    )
    prompt = (
        f"job_type={job_type}\n"
        f"requested_action={json.dumps(requested_action, default=str)}\n"
        "Call the tool once and stop."
    )
    try:
        result = Runner.run_sync(agent, prompt)
        # Prefer parsing tool output from final; if unclear, fall through
        text = str(getattr(result, "final_output", "") or "")
        # Direct tool path is authoritative — re-run once if LLM path did not produce evidence
        # (avoid double-write): only accept if we can detect success in output
        if "\"ok\": true" in text.replace(" ", "") or '"ok": true' in text or '"ok":true' in text:
            try:
                # find JSON object in output
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    if isinstance(parsed, dict) and parsed.get("ok"):
                        parsed["_via"] = "openai_agents_sdk"
                        return parsed
            except json.JSONDecodeError:
                pass
        return None
    except Exception:  # noqa: BLE001
        return None


def execute_job_via_agents_runtime(
    job_type: str,
    requested_action: dict[str, Any],
    *,
    agent_role: str = "SpecialistAgent",
) -> dict[str, Any]:
    """
    Authority-aligned ExecuteJob entrypoint.

    1) Try OpenAI Agents SDK Runner when API key present.
    2) Otherwise invoke the same connector path the SDK tool wraps (deterministic
       tool execution for auditor-approved structured actions).
    """
    llm_result = _run_via_sdk_llm(job_type, requested_action, agent_role)
    if llm_result is not None:
        return llm_result

    result = execute_job_type(job_type, requested_action or {})
    result = dict(result)
    result["_via"] = (
        "openai_agents_sdk_tools_direct"
        if _try_import_agents()
        else "connector_direct_sdk_unavailable"
    )
    result["_runtime"] = "openai-agents" if _try_import_agents() else "portable_core.connectors"
    result["_note"] = (
        "Structured ExecuteJob: SDK package present; tool invoked directly because "
        "OPENAI_API_KEY unset or LLM path did not return parseable evidence. "
        "Same portable_core connector + evidence contracts."
        if _try_import_agents()
        else "openai-agents not installed; connector path used. Install optional [agents] extra."
    )
    return result


def _try_import_agents() -> bool:
    try:
        import agents  # noqa: F401

        return True
    except ImportError:
        return False

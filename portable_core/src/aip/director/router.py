"""DirectorAgent routing — general catalog routing (anti-example-coding).

Classifies a signal/objective against the *live* agent catalog + scopes.
Never hardcodes scenario trees (mail≠always Gmail+GitHub, etc.).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from aip.evidence.contracts import JOB_TYPE_SYSTEM, has_evidence_contract


@dataclass
class ProposedJob:
    agent_id: str
    job_type: str
    requested_action: dict[str, Any]
    confidence: float
    rationale: str
    title: str = ""


@dataclass
class RoutingDecision:
    jobs: list[ProposedJob] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def route(
    *,
    agents: list[dict[str, Any]],
    workspace: dict[str, Any],
    objectives: list[str],
    plan: list[dict[str, Any]] | None = None,
    signal: dict[str, Any] | None = None,
) -> RoutingDecision:
    """
    Produce candidate jobs from live catalog.

    Priority:
    1. Structured `plan` entries (human/API-provided objectives — still audited).
    2. Structured `signal.requested_jobs` if present.
    3. LLM classification against catalog when OPENAI_API_KEY set.
    4. Otherwise empty decision with note (no inventing example paths).
    """
    executable = [
        a
        for a in agents
        if a.get("status") not in ("unsupported", "disabled", "error")
        and a.get("activation", "ready") == "ready"
        and a.get("role") != "ValidationAgent"
        and a.get("role") != "DirectorAgent"
    ]

    # 1) Explicit plan
    if plan:
        return _from_structured_plan(plan, executable, workspace)

    # 2) Signal-carried structured jobs
    signal = signal or {}
    if isinstance(signal.get("requested_jobs"), list) and signal["requested_jobs"]:
        return _from_structured_plan(signal["requested_jobs"], executable, workspace)

    # 3) Objectives that are JSON job objects
    structured_from_obj: list[dict[str, Any]] = []
    for obj in objectives:
        if isinstance(obj, dict):
            structured_from_obj.append(obj)
            continue
        text = str(obj).strip()
        if text.startswith("{"):
            try:
                structured_from_obj.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    if structured_from_obj:
        return _from_structured_plan(structured_from_obj, executable, workspace)

    # 4) LLM
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if api_key and (objectives or signal):
        try:
            return _llm_route(api_key, executable, workspace, objectives, signal)
        except Exception as exc:  # noqa: BLE001
            return RoutingDecision(notes=[f"LLM routing failed: {exc}"])

    return RoutingDecision(
        notes=[
            "Director: no structured plan/signal jobs and no LLM key — "
            "refusing to invent example-specific routes. Provide plan[] or OPENAI_API_KEY."
        ]
    )


def _match_agent(executable: list[dict[str, Any]], *, agent_id: str | None, role: str | None, system: str | None) -> dict[str, Any] | None:
    if agent_id:
        for a in executable:
            if a.get("id") == agent_id:
                return a
    if role:
        for a in executable:
            if a.get("role") == role:
                return a
    if system:
        for a in executable:
            if a.get("systemKey") == system or a.get("system_key") == system:
                return a
    return None


def _from_structured_plan(
    plan: list[dict[str, Any]],
    executable: list[dict[str, Any]],
    workspace: dict[str, Any],
) -> RoutingDecision:
    jobs: list[ProposedJob] = []
    notes: list[str] = []
    for i, item in enumerate(plan):
        if not isinstance(item, dict):
            notes.append(f"plan[{i}] skipped (not object)")
            continue
        job_type = str(item.get("job_type") or item.get("jobType") or "").strip()
        if not job_type:
            notes.append(f"plan[{i}] missing job_type")
            continue
        system = JOB_TYPE_SYSTEM.get(job_type)
        agent = _match_agent(
            executable,
            agent_id=item.get("agent_id") or item.get("agentId"),
            role=item.get("agent_role") or item.get("role"),
            system=system,
        )
        if not agent:
            notes.append(f"plan[{i}] no executable agent for {job_type}")
            continue
        action = item.get("requested_action") or item.get("requestedAction") or {}
        if not isinstance(action, dict):
            action = {"raw": action}
        # Fill smoke defaults from workspace scope when fields absent (general, not hardcoding demo)
        action = _enrich_action_from_scope(job_type, action, workspace)
        jobs.append(
            ProposedJob(
                agent_id=str(agent["id"]),
                job_type=job_type,
                requested_action=action,
                confidence=float(item.get("confidence") or 1.0),
                rationale=str(item.get("rationale") or "Structured plan entry"),
                title=str(item.get("title") or job_type),
            )
        )
    return RoutingDecision(jobs=jobs, notes=notes)


def _enrich_action_from_scope(job_type: str, action: dict[str, Any], workspace: dict[str, Any]) -> dict[str, Any]:
    out = dict(action)
    scope = workspace.get("scope") or {}
    if job_type.startswith("github.") and "repo" not in out:
        repos = scope.get("repos") or workspace.get("repo_scope") or []
        if repos:
            full = str(repos[0])
            if "/" in full:
                owner, repo = full.split("/", 1)
                out.setdefault("owner", owner)
                out.setdefault("repo", repo)
                out.setdefault("repo_full", full)
    if job_type.startswith("jira.") and "project_key" not in out and "projectKey" not in out:
        keys = scope.get("jiraKeys") or workspace.get("jira_scope") or []
        if keys:
            out.setdefault("project_key", str(keys[0]))
    if job_type.startswith("calendar.") and "calendar_id" not in out:
        cals = scope.get("calendars") or workspace.get("calendar_scope") or []
        out.setdefault("calendar_id", str(cals[0]) if cals else "primary")
    if job_type.startswith("gmail.") and "to" not in out:
        groups = scope.get("emailGroups") or workspace.get("comms_scope") or []
        if groups:
            out.setdefault("to", str(groups[0]))
    return out


def _llm_route(
    api_key: str,
    executable: list[dict[str, Any]],
    workspace: dict[str, Any],
    objectives: list[str],
    signal: dict[str, Any],
) -> RoutingDecision:
    from openai import OpenAI

    catalog = [
        {
            "agent_id": a.get("id"),
            "role": a.get("role"),
            "system": a.get("systemKey") or a.get("system_key"),
            "tool_scope": a.get("toolScope") or a.get("tool_scope") or [],
            "job_types": [
                t for t in (a.get("toolScope") or a.get("tool_scope") or []) if has_evidence_contract(t)
            ],
        }
        for a in executable
    ]
    prompt = (
        "Select a small set of specialist jobs for this run from the live agent catalog only.\n"
        "Return JSON {\"jobs\":[{\"agent_id\":...,\"job_type\":...,\"requested_action\":{},"
        "\"confidence\":0-1,\"rationale\":...}]}.\n"
        "Do not invent agents or systems. Prefer the minimum set that satisfies objectives.\n"
        f"Catalog: {json.dumps(catalog)}\n"
        f"Workspace scope: {json.dumps(workspace.get('scope') or {})}\n"
        f"Objectives: {objectives}\n"
        f"Signal: {json.dumps(signal)[:2000]}"
    )
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text)
    return _from_structured_plan(list(data.get("jobs") or []), executable, workspace)

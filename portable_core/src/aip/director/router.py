"""DirectorAgent routing — general catalog routing (anti-example-coding).

Classifies a signal/objective against the *live* agent catalog + scopes.
Never hardcodes scenario trees (mail≠always Gmail+GitHub, etc.).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from aip.evidence.contracts import JOB_TYPE_SYSTEM, has_evidence_contract
from aip.llm.client import llm_configured

_GITHUB_ISSUE_MANAGER_ALIASES: dict[str, str] = {
    "github.comment_issue": "github.create_issue",
}


def _agent_has_job_type(agent: dict[str, Any], job_type: str) -> bool:
    tools = agent.get("toolScope") or agent.get("tool_scope") or []
    if job_type in tools:
        return True
    alias = _GITHUB_ISSUE_MANAGER_ALIASES.get(job_type)
    return bool(alias and alias in tools)


def _split_github_repo(full: str) -> tuple[str, str]:
    if "/" not in full:
        return "", full
    owner, name = full.split("/", 1)
    return owner.strip(), name.strip()


def _github_jobs_from_signal(signal: dict[str, Any]) -> list[dict[str, Any]]:
    """Event-family → catalog job from GitHub webhook facts (not scenario trees)."""
    if str(signal.get("channel") or "") != "github":
        return []
    event = str(signal.get("event") or "").lower()
    repo_full = str(signal.get("repo") or "").strip()
    if not repo_full or "/" not in repo_full:
        return []
    owner, repo_name = _split_github_repo(repo_full)
    title = str(signal.get("title") or "").strip()
    html_url = str(signal.get("html_url") or "").strip()

    if event == "pull_request":
        pr_number = signal.get("pull_number")
        if pr_number is None:
            return []
        action: dict[str, Any] = {
            "owner": owner,
            "repo": repo_name,
            "repo_full": repo_full,
            "pull_number": pr_number,
        }
        if title:
            action["title"] = title
        if html_url:
            action["pr_url"] = html_url
        return [
            {
                "job_type": "github.review_pr",
                "requested_action": action,
                "rationale": "GitHub pull_request signal facts",
                "title": title or f"Review PR #{pr_number}",
            }
        ]

    if event == "issues":
        issue_number = signal.get("issue_number")
        if issue_number is None:
            return []
        action = {
            "owner": owner,
            "repo": repo_name,
            "repo_full": repo_full,
            "issue_number": issue_number,
        }
        if title:
            action["title"] = title
        if html_url:
            action["issue_url"] = html_url
        return [
            {
                "job_type": "github.comment_issue",
                "requested_action": action,
                "rationale": "GitHub issues signal facts (comment on existing issue)",
                "title": title or f"Comment on issue #{issue_number}",
            }
        ]

    return []


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
    3. GitHub webhook signal facts → catalog job types (issues/PR families).
    4. Objectives that are JSON job objects.
    5. LLM classification against catalog when OPENAI/OpenRouter key set.
    6. Otherwise empty decision with note (no inventing example paths).
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
    signal = signal or {}
    if plan:
        return _from_structured_plan(plan, executable, workspace, signal=signal)

    # 2) Signal-carried structured jobs
    if isinstance(signal.get("requested_jobs"), list) and signal["requested_jobs"]:
        return _from_structured_plan(signal["requested_jobs"], executable, workspace, signal=signal)

    # 3) GitHub webhook facts → catalog jobs (defense if normalize missed requested_jobs)
    github_from_signal = _github_jobs_from_signal(signal)
    if github_from_signal:
        return _from_structured_plan(github_from_signal, executable, workspace, signal=signal)

    # 4) Objectives that are JSON job objects
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
        return _from_structured_plan(structured_from_obj, executable, workspace, signal=signal)

    # 5) LLM (OPENAI_API_KEY or OPENROUTER_API_KEY + LLM_API_BASE)
    if llm_configured() and (objectives or signal):
        try:
            return _llm_route(executable, workspace, objectives, signal)
        except Exception as exc:  # noqa: BLE001
            return RoutingDecision(notes=[f"LLM routing failed: {exc}"])

    return RoutingDecision(
        notes=[
            "Director: no structured plan/signal jobs and no LLM key — "
            "refusing to invent example-specific routes. Provide plan[] or "
            "OPENAI_API_KEY / OPENROUTER_API_KEY."
        ]
    )


def _match_agent(executable: list[dict[str, Any]], *, agent_id: str | None, role: str | None, system: str | None, job_type: str | None = None) -> dict[str, Any] | None:
    if agent_id:
        for a in executable:
            if a.get("id") == agent_id:
                return a
    if role:
        for a in executable:
            if a.get("role") == role:
                return a
    # Prefer agent whose tool allowlist includes this job_type (specialization match)
    if job_type:
        for a in executable:
            if _agent_has_job_type(a, job_type):
                if system:
                    if a.get("systemKey") == system or a.get("system_key") == system:
                        return a
                else:
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
    *,
    signal: dict[str, Any] | None = None,
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
            job_type=job_type,
        )
        if not agent:
            notes.append(f"plan[{i}] no executable agent for {job_type}")
            continue
        action = item.get("requested_action") or item.get("requestedAction") or {}
        if not isinstance(action, dict):
            action = {"raw": action}
        # Fill defaults from webhook signal, then workspace scope (general, not hardcoding demo)
        action = _enrich_action_from_scope(job_type, action, workspace, signal=signal)
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


def _enrich_action_from_scope(
    job_type: str,
    action: dict[str, Any],
    workspace: dict[str, Any],
    *,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(action)
    sig = signal or {}
    if job_type.startswith("github."):
        repo_val = str(out.get("repo") or "").strip()
        if repo_val and "/" in repo_val and not out.get("owner"):
            owner, repo_name = repo_val.split("/", 1)
            out["owner"] = owner.strip()
            out["repo"] = repo_name.strip()
            out.setdefault("repo_full", repo_val)
        # Webhook signal facts override workspace scope for inbound GitHub events
        sig_repo = str(sig.get("repo") or "").strip()
        if sig_repo and "/" in sig_repo:
            o, r = _split_github_repo(sig_repo)
            out["owner"] = o
            out["repo"] = r
            out["repo_full"] = sig_repo
        if sig.get("issue_number") is not None:
            out.setdefault("issue_number", sig["issue_number"])
        if sig.get("pull_number") is not None:
            out.setdefault("pull_number", sig["pull_number"])
        if sig.get("title"):
            out.setdefault("title", sig["title"])
        if sig.get("html_url"):
            out.setdefault("issue_url", sig["html_url"])
            out.setdefault("pr_url", sig["html_url"])
    scope = workspace.get("scope") or {}
    if job_type.startswith("github.") and "repo" not in out and "owner" not in out:
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
    executable: list[dict[str, Any]],
    workspace: dict[str, Any],
    objectives: list[str],
    signal: dict[str, Any],
) -> RoutingDecision:
    from aip.llm.client import chat_completion_json

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
    data = chat_completion_json(
        system="You output only valid JSON.",
        user=prompt,
        temperature=0.2,
    )
    if not isinstance(data, dict):
        return RoutingDecision(notes=["LLM routing returned non-object JSON"])
    return _from_structured_plan(list(data.get("jobs") or []), executable, workspace, signal=signal)

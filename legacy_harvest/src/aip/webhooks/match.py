"""Deterministic tool name → webhook id matching (no LLM, no URLs)."""

from __future__ import annotations

from typing import Any

from aip.webhooks.gmail_inventory import gmail_webhook_seed
from aip.webhooks.github_inventory import github_webhook_seed
from aip.webhooks.jira_inventory import jira_webhook_seed

PR_EVENTS = (
    "pull_request.opened",
    "pull_request.synchronize",
    "pull_request.reopened",
)
ISSUE_EVENTS = ("issues.opened", "issue_comment.created")
CICD_EVENTS = ("workflow_run.completed",)
JIRA_ISSUE_EVENTS = ("jira:issue_created", "jira:issue_updated")
JIRA_COMMENT_EVENTS = ("comment_created",)
GMAIL_EVENTS = ("gmail.message",)

_GMAIL_NAMES = frozenset(
    {"fetch_email", "search_emails", "send_email", "send_email_reply"}
)
_CALENDAR_NAMES = frozenset(
    {
        "list_events",
        "create_event",
        "update_event",
        "delete_event",
        "list_calendars",
        "freebusy",
    }
)


def known_webhook_ids() -> frozenset[str]:
    ids = {w.id for w in github_webhook_seed()}
    ids.update(w.id for w in jira_webhook_seed())
    ids.update(w.id for w in gmail_webhook_seed())
    return frozenset(ids)


def system_for_tool_name(name: str) -> str | None:
    return _infer_system(name)


def connected_system_for_webhook(webhook_id: str) -> str:
    wid = (webhook_id or "").strip()
    if wid.startswith("gmail.") or wid in GMAIL_EVENTS:
        return "gmail"
    if wid.startswith("jira:") or wid in {"comment_created", "comment_updated"}:
        return "jira"
    return "github"


def _row_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "").strip()


def _row_system(row: dict[str, Any]) -> str:
    return str(row.get("connected_system_id") or "").strip().lower()


def _row_toolset(row: dict[str, Any]) -> str:
    return str(row.get("toolset") or "").strip().lower()


def _row_tags(row: dict[str, Any]) -> list[str]:
    tags = row.get("capability_tags") or []
    if not isinstance(tags, list):
        return []
    return [str(tag).lower() for tag in tags]


def _infer_system(name: str) -> str | None:
    n = name.lower()
    if name in _GMAIL_NAMES or n.startswith("gmail"):
        return "gmail"
    if name in _CALENDAR_NAMES or "calendar" in n or n.startswith("freebusy"):
        return "calendar"
    if "jira" in n or "atlassian" in n or "jql" in n:
        return "jira"
    if "github" in n or "pull_request" in n or "merge_pull_request" in n:
        return "github"
    return None


def _infer_toolset(name: str, system: str) -> str:
    n = name.lower()
    if system == "gmail":
        return "email"
    if system == "calendar":
        return "calendar"
    if system == "jira":
        if "comment" in n:
            return "comment"
        return "issue"
    if "workflow" in n or "check_run" in n or "check_suite" in n or "action" in n:
        return "actions"
    if "pull" in n or "pr_" in n or "review" in n or "merge" in n:
        return "pull_requests"
    if "issue" in n:
        return "issues"
    return "repos"


def wake_intents_for_opportunity(
    *,
    title: str = "",
    role: str = "",
    tool_names: list[str] | None = None,
    systems: list[str] | None = None,
) -> list[str]:
    """Derive wake intents from opportunity role/title, not from incidental tool tokens."""
    text = f"{title} {role}".lower()
    tools = {(name or "").strip().lower() for name in (tool_names or []) if name}
    system_set = {(s or "").strip().lower() for s in (systems or []) if s}
    intents: list[str] = []

    def add(intent: str) -> None:
        if intent not in intents:
            intents.append(intent)

    pr_tools = any(
        "pull_request" in t or t.startswith("merge_pull") or "pr_" in t for t in tools
    )
    issue_tools = any(
        t in {"issue_read", "search_issues", "create_issue", "list_issues"}
        or (t.startswith("issue_") and "pull" not in t)
        for t in tools
    )
    title_is_pr = (
        "pull" in text
        or " pr " in f" {text} "
        or "reviewer" in text
        or "code review" in text
    )
    title_is_issue = "issue" in text or "triage" in text
    if title_is_pr or pr_tools:
        add("pull_request")
    # Context tools like issue_read on a PR reviewer must not widen wake scope.
    if title_is_issue or (issue_tools and "pull_request" not in intents):
        add("issue")
    if "cicd" in text or "ci/cd" in text or "workflow" in text:
        add("cicd")
    if "jira" in text or "jira" in system_set or any("jira" in t for t in tools):
        add("jira")
    if (
        "gmail" in text
        or "email" in text
        or "mail" in text
        or "gmail" in system_set
        or any(t in _GMAIL_NAMES for t in tools)
    ):
        add("gmail")
    return intents


def webhooks_for_tools(
    tool_names: list[str],
    catalog: list[dict[str, Any]] | None = None,
    *,
    wake_intents: list[str] | None = None,
) -> list[str]:
    """Return portable catalog webhook ids for the given spec tool names."""
    by_name: dict[str, dict[str, Any]] = {}
    for row in catalog or []:
        if not isinstance(row, dict):
            continue
        name = _row_name(row)
        if name:
            by_name[name] = row

    systems: set[str] = set()
    toolsets: set[str] = set()
    tags: set[str] = set()
    for raw in tool_names:
        name = (raw or "").strip()
        if not name:
            continue
        row = by_name.get(name)
        system = _row_system(row) if row else _infer_system(name)
        if not system:
            continue
        systems.add(system)
        toolset = _row_toolset(row) if row else ""
        if not toolset:
            toolset = _infer_toolset(name, system)
        toolsets.add(toolset)
        tags.update(_row_tags(row) if row else [])
        tags.update(name.lower().replace("-", "_").split("_"))

    intents = {
        str(item).strip().lower()
        for item in (wake_intents or [])
        if str(item).strip()
    }
    if not intents:
        intents = set(
            wake_intents_for_opportunity(tool_names=tool_names, systems=list(systems))
        )
    if intents & {"pull_request", "issue", "cicd"}:
        systems.add("github")

    found: list[str] = []

    def add(events: tuple[str, ...] | list[str]) -> None:
        for event in events:
            if event not in found:
                found.append(event)

    githubish = "github" in systems or bool(
        toolsets & {"pull_requests", "issues", "actions", "repos"}
    )
    explicit = wake_intents is not None
    if githubish and (
        "pull_request" in intents
        or (
            not explicit
            and (
                "pull_requests" in toolsets
                or "github_pr_review" in tags
            )
        )
    ):
        add(PR_EVENTS)
        # PR conversation comments arrive as issue_comment; filtered at dispatch.
        add(("issue_comment.created",))
    # Issue wake requires explicit issue intent when intents are provided.
    if githubish and (
        "issue" in intents
        or (
            not explicit
            and (
                "issues" in toolsets
                or "github_issue_resolve" in tags
            )
        )
    ):
        add(ISSUE_EVENTS)
    if githubish and (
        "cicd" in intents
        or "actions" in toolsets
        or "ci_cd" in tags
        or "workflow" in tags
        or "cicd" in tags
    ):
        add(CICD_EVENTS)

    if "jira" in systems or "jira" in intents:
        add(JIRA_ISSUE_EVENTS)
        if "comment" in toolsets or any("comment" in t for t in tags):
            add(JIRA_COMMENT_EVENTS)

    if "gmail" in systems or "gmail" in intents:
        add(GMAIL_EVENTS)

    # Calendar-only specs do not wake on a webhook.
    return found

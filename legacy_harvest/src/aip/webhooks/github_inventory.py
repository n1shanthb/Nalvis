"""Static GitHub webhook event inventory (seed for Webhook Catalog)."""

from __future__ import annotations

from aip.webhooks.models import EnterpriseWebhook

# Common actions per event. Empty actions → catalog id is just the event name.
_GITHUB_EVENTS: dict[str, list[str]] = {
    "branch_protection_configuration": ["enabled", "disabled"],
    "branch_protection_rule": ["created", "edited", "deleted"],
    "check_run": ["created", "rerequested", "completed", "requested_action"],
    "check_suite": ["completed", "requested", "rerequested"],
    "code_scanning_alert": [
        "appeared_in_branch",
        "closed_by_user",
        "created",
        "fixed",
        "reopened",
        "reopened_by_user",
    ],
    "commit_comment": ["created"],
    "create": [],
    "custom_property": ["created", "deleted", "updated"],
    "custom_property_values": ["updated"],
    "delete": [],
    "dependabot_alert": [
        "created",
        "dismissed",
        "fixed",
        "reintroduced",
        "reopened",
    ],
    "deploy_key": ["created", "deleted"],
    "deployment": ["created"],
    "deployment_protection_rule": ["requested"],
    "deployment_review": ["approved", "rejected", "requested"],
    "deployment_status": ["created"],
    "discussion": [
        "answered",
        "category_changed",
        "closed",
        "created",
        "deleted",
        "edited",
        "labeled",
        "locked",
        "pinned",
        "reopened",
        "transferred",
        "unanswered",
        "unlabeled",
        "unlocked",
        "unpinned",
    ],
    "discussion_comment": ["created", "deleted", "edited"],
    "fork": [],
    "github_app_authorization": ["revoked"],
    "gollum": [],
    "installation": [
        "created",
        "deleted",
        "new_permissions_accepted",
        "suspend",
        "unsuspend",
    ],
    "installation_repositories": ["added", "removed"],
    "installation_target": ["renamed"],
    "issue_comment": ["created", "deleted", "edited"],
    "issues": [
        "assigned",
        "closed",
        "deleted",
        "demilestoned",
        "edited",
        "labeled",
        "locked",
        "milestoned",
        "opened",
        "pinned",
        "reopened",
        "transferred",
        "unassigned",
        "unlabeled",
        "unlocked",
        "unpinned",
    ],
    "label": ["created", "deleted", "edited"],
    "marketplace_purchase": [
        "cancelled",
        "changed",
        "pending_change",
        "pending_change_cancelled",
        "purchased",
    ],
    "member": ["added", "edited", "removed"],
    "membership": ["added", "removed"],
    "merge_group": ["checks_requested", "destroyed"],
    "meta": ["deleted"],
    "milestone": ["closed", "created", "deleted", "edited", "opened"],
    "org_block": ["blocked", "unblocked"],
    "organization": [
        "deleted",
        "member_added",
        "member_invited",
        "member_removed",
        "renamed",
    ],
    "package": ["published", "updated"],
    "page_build": [],
    "ping": [],
    "project_card": [
        "converted",
        "created",
        "deleted",
        "edited",
        "moved",
        "converted",
    ],
    "project_column": ["created", "deleted", "edited", "moved"],
    "project": ["closed", "created", "deleted", "edited", "reopened"],
    "projects_v2": ["created", "deleted", "edited"],
    "projects_v2_item": [
        "archived",
        "converted",
        "created",
        "deleted",
        "edited",
        "reordered",
        "restored",
    ],
    "public": [],
    "pull_request": [
        "assigned",
        "auto_merge_disabled",
        "auto_merge_enabled",
        "closed",
        "converted_to_draft",
        "demilestoned",
        "dequeued",
        "edited",
        "enqueued",
        "labeled",
        "locked",
        "milestoned",
        "opened",
        "ready_for_review",
        "reopened",
        "review_request_removed",
        "review_requested",
        "synchronize",
        "unassigned",
        "unlabeled",
        "unlocked",
    ],
    "pull_request_review_comment": ["created", "deleted", "edited"],
    "pull_request_review": ["dismissed", "edited", "submitted"],
    "pull_request_review_thread": ["resolved", "unresolved"],
    "push": [],
    "registry_package": ["published", "updated"],
    "release": [
        "created",
        "deleted",
        "edited",
        "prereleased",
        "published",
        "released",
        "unpublished",
    ],
    "repository": [
        "archived",
        "created",
        "deleted",
        "edited",
        "privatized",
        "publicized",
        "renamed",
        "transferred",
        "unarchived",
    ],
    "repository_dispatch": [],
    "repository_ruleset": ["created", "deleted", "edited"],
    "repository_vulnerability_alert": ["create", "dismiss", "reopen", "resolve"],
    "secret_scanning_alert": [
        "created",
        "reopened",
        "resolved",
        "revoked",
        "validated",
    ],
    "secret_scanning_alert_location": ["created"],
    "security_advisory": ["published", "updated", "withdrawn"],
    "sponsorship": [
        "cancelled",
        "created",
        "edited",
        "pending_cancellation",
        "pending_tier_change",
        "tier_changed",
    ],
    "star": ["created", "deleted"],
    "status": [],
    "team": ["added_to_repository", "created", "deleted", "edited", "removed_from_repository"],
    "team_add": [],
    "watch": ["started"],
    "workflow_dispatch": [],
    "workflow_job": ["completed", "in_progress", "queued", "waiting"],
    "workflow_run": [
        "completed",
        "in_progress",
        "requested",
    ],
}

_CAP_HINTS: dict[str, list[str]] = {
    "pull_request": ["github_pr_review", "code_review"],
    "pull_request_review": ["github_pr_review"],
    "pull_request_review_comment": ["github_pr_review", "mention_reply"],
    "issue_comment": ["mention_reply", "issue_triage", "ci_cd_author"],
    "issues": ["issue_triage", "issue_responder", "ci_cd_author"],
    "push": ["ci_notify"],
    "release": ["release_notes"],
    "ping": ["health"],
    "workflow_run": ["ci_cd", "github_cicd_doctor"],
    "workflow_job": ["ci_cd"],
    "check_run": ["ci_cd"],
    "check_suite": ["ci_cd"],
}


def webhook_id(event: str, action: str = "") -> str:
    event = (event or "").strip().lower()
    action = (action or "").strip().lower()
    if action:
        return f"{event}.{action}"
    return event


def github_webhook_seed(system_id: str = "github") -> list[EnterpriseWebhook]:
    """Full static inventory of GitHub webhook event/action pairs."""
    out: list[EnterpriseWebhook] = []
    seen: set[str] = set()
    for event, actions in sorted(_GITHUB_EVENTS.items()):
        caps = list(_CAP_HINTS.get(event, [event.replace("_", "-")]))
        if not actions:
            wid = webhook_id(event)
            if wid not in seen:
                seen.add(wid)
                out.append(
                    EnterpriseWebhook(
                        connected_system_id=system_id,
                        id=wid,
                        event=event,
                        action="",
                        description=f"GitHub webhook event `{event}`",
                        capability_tags=caps,
                    )
                )
            continue
        for action in actions:
            wid = webhook_id(event, action)
            if wid in seen:
                continue
            seen.add(wid)
            out.append(
                EnterpriseWebhook(
                    connected_system_id=system_id,
                    id=wid,
                    event=event,
                    action=action,
                    description=f"GitHub `{event}` / `{action}`",
                    capability_tags=caps,
                )
            )
    return out

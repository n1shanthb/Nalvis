"""Orchestration package — import workflows/activities from their modules.

Keep this __init__ lazy so Temporal workflow sandbox does not pull SQLAlchemy
via activities when loading workflow modules.
"""

from __future__ import annotations

from typing import Any


def get_workflows() -> list[Any]:
    from aip.orchestration.workflows import (
        CompanyRunWorkflow,
        GithubInboundWorkflow,
        GmailInboundWorkflow,
        ProductRunWorkflow,
        ValidationWorkflow,
    )

    return [
        CompanyRunWorkflow,
        ProductRunWorkflow,
        ValidationWorkflow,
        GmailInboundWorkflow,
        GithubInboundWorkflow,
    ]


def get_activities() -> list[Any]:
    from aip.orchestration.activities import (
        create_hil_approval_activity,
        director_route_activity,
        draft_job_content_activity,
        ensure_schema,
        evaluate_policy_activity,
        execute_job_activity,
        fail_job_activity,
        fetch_gmail_inbound_signal_activity,
        ingest_kg_activity,
        mark_run_status_activity,
        normalize_github_webhook_signal_activity,
        start_company_run_from_signal_activity,
        validate_job_activity,
    )

    return [
        ensure_schema,
        ingest_kg_activity,
        director_route_activity,
        evaluate_policy_activity,
        create_hil_approval_activity,
        draft_job_content_activity,
        execute_job_activity,
        validate_job_activity,
        mark_run_status_activity,
        fail_job_activity,
        fetch_gmail_inbound_signal_activity,
        normalize_github_webhook_signal_activity,
        start_company_run_from_signal_activity,
    ]


__all__ = ["get_activities", "get_workflows"]

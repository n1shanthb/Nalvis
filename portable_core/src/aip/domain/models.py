"""Authoritative domain schemas (Authority.md nouns) for Phase 0+."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from aip.validation.verdicts import AuthorityVerdict


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED_FOR_APPROVAL = "blocked_for_approval"


class Workspace(BaseModel):
    """Product workspace under the single-tenant company."""

    workspace_id: str
    name: str
    company_id: str = "default"
    repo_scope: list[str] = Field(default_factory=list)
    jira_scope: list[str] = Field(default_factory=list)
    comms_scope: list[str] = Field(default_factory=list)
    calendar_scope: list[str] = Field(default_factory=list)
    policies: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Machine-checkable identifiers/URLs proving external work happened."""

    job_type: str = ""
    refs: dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime | None = None


class ValidationOutcome(BaseModel):
    """Public Authority verdict surface."""

    verdict: AuthorityVerdict = "NO_EVIDENCE"
    confidence: float = 0.0
    message: str = ""
    evidence: Evidence = Field(default_factory=Evidence)
    checked_at: datetime | None = None


class Job(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    job_type: str
    agent_id: str | None = None
    requested_action: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    evidence: Evidence | None = None
    validation: ValidationOutcome | None = None
    error: str | None = None
    idempotency_key: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Run(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    company_id: str = "default"
    status: Literal["queued", "running", "succeeded", "failed", "partial"] = "queued"
    objectives: list[str] = Field(default_factory=list)
    workspace_ids: list[str] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)
    temporal_workflow_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

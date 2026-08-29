"""Postgres ORM tables — Authority domain nouns + ops console fields."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    name: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ContextDocumentRow(Base):
    __tablename__ = "context_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"ctx-{uuid4().hex[:12]}")
    company_id: Mapped[str] = mapped_column(String(64), ForeignKey("companies.id"), default="default")
    name: Mapped[str] = mapped_column(String(256), default="")
    source: Mapped[str] = mapped_column(String(32), default="paste")
    raw: Mapped[str] = mapped_column(Text, default="")
    parse_preview: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    workspace_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(64), ForeignKey("companies.id"), default="default")
    name: Mapped[str] = mapped_column(String(256))
    product: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    repo_scope: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    jira_scope: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    comms_scope: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    calendar_scope: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"agt-{uuid4().hex[:12]}")
    company_id: Mapped[str] = mapped_column(String(64), ForeignKey("companies.id"), default="default")
    name: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    mission: Mapped[str] = mapped_column(Text, default="")
    tool_scope: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    workspace_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    # active | idle | disabled | error | unsupported
    status: Mapped[str] = mapped_column(String(32), default="idle")
    activation: Mapped[str] = mapped_column(String(64), default="ready")
    system_key: Mapped[str] = mapped_column(String(64), default="")  # github|jira|gmail|calendar|slack|...
    origin: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    specs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    guardrails: Mapped[list[AgentGuardrailRow]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentGuardrailRow(Base):
    __tablename__ = "agent_guardrails"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"gr-{uuid4().hex[:12]}")
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id", ondelete="CASCADE"))
    tool: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(32), default="allow")  # allow|hil|deny|auto
    label: Mapped[str] = mapped_column(String(256), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="synthesized")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    agent: Mapped[AgentRow] = relationship(back_populates="guardrails")


class PolicyRow(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("workspace_id", "action", name="uq_policy_ws_action"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(256), default="")
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    hil_required: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_merge: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(String(64), ForeignKey("companies.id"), default="default")
    title: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    objectives: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    workspace_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    temporal_workflow_id: Mapped[str] = mapped_column(String(256), default="")
    # Optional structured plan / signal payload for Director (not demo-hardcoded)
    plan: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    signal: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    jobs: Mapped[list[JobRow]] = relationship(back_populates="run", cascade="all, delete-orphan")


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_run_id", "run_id"),
        Index("ix_jobs_workspace_id", "workspace_id"),
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"))
    agent_id: Mapped[str] = mapped_column(String(64), default="")
    job_type: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    requested_action: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    run: Mapped[RunRow] = relationship(back_populates="jobs")


class ApprovalRow(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"appr-{uuid4().hex[:12]}")
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("jobs.id", ondelete="CASCADE"))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(String(64))
    agent_id: Mapped[str] = mapped_column(String(64), default="")
    job_type: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512), default="")
    intent_summary: Mapped[str] = mapped_column(Text, default="")
    diff_preview: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    decision: Mapped[str] = mapped_column(String(32), default="pending")
    edited_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ValidationRow(Base):
    __tablename__ = "validations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"val-{uuid4().hex[:12]}")
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("jobs.id", ondelete="CASCADE"))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(String(64))
    agent_id: Mapped[str] = mapped_column(String(64), default="")
    job_type: Mapped[str] = mapped_column(String(128))
    verdict: Mapped[str] = mapped_column(String(32), default="NO_EVIDENCE")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    checks: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_run_id", "run_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"evt-{uuid4().hex[:12]}")
    run_id: Mapped[str] = mapped_column(String(64), default="")
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), default="queued")
    label: Mapped[str] = mapped_column(String(512), default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

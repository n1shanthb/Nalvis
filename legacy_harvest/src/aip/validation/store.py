"""SQLite persistence for validation records and response watches."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from sqlmodel import Field, SQLModel, col, select

from aip.persistence.db import get_engine, get_session
from aip.validation.models import CheckMarks, ValidationRecord


class ValidationRecordRow(SQLModel, table=True):
    __tablename__ = "validation_record"

    record_id: str = Field(primary_key=True)
    execution_id: Optional[str] = Field(default=None, index=True)
    watch_id: Optional[str] = Field(default=None, index=True)
    spec_id: str = Field(default="", index=True)
    project_id: str = Field(default="", index=True)
    system: str = Field(default="")
    objective: str = Field(default="")
    verdict: str = Field(default="INSUFFICIENT_EVIDENCE", index=True)
    confidence: float = Field(default=0.0)
    claimed_action: str = Field(default="")
    expected: str = Field(default="")
    observed: str = Field(default="")
    check_marks_json: str = Field(default="{}")
    evidence_refs_json: str = Field(default="{}")
    message: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResponseWatchRow(SQLModel, table=True):
    __tablename__ = "validation_response_watch"

    watch_id: str = Field(primary_key=True)
    delivery_key: str = Field(index=True)
    system: str = Field(default="")
    project_id: str = Field(default="", index=True)
    expected_spec_ids_json: str = Field(default="[]")
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deadline_at: datetime = Field(index=True)
    status: str = Field(default="open", index=True)
    satisfied_spec_id: str = Field(default="")
    skip_reason: str = Field(default="")
    subject: str = Field(default="")


def ensure_validation_tables() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def _marks_to_json(marks: CheckMarks) -> str:
    return json.dumps(marks.model_dump())


def _marks_from_json(raw: str) -> CheckMarks:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return CheckMarks()
    return CheckMarks.model_validate(data) if isinstance(data, dict) else CheckMarks()


class ValidationStore:
    def ensure_tables(self) -> None:
        ensure_validation_tables()

    def upsert_record(self, record: ValidationRecord) -> ValidationRecordRow:
        self.ensure_tables()
        now = datetime.now(timezone.utc)
        with get_session() as session:
            row: ValidationRecordRow | None = None
            if record.execution_id:
                stmt = select(ValidationRecordRow).where(
                    ValidationRecordRow.execution_id == record.execution_id
                )
                row = session.exec(stmt).first()
            if row is None and record.watch_id:
                stmt = select(ValidationRecordRow).where(
                    ValidationRecordRow.watch_id == record.watch_id,
                    ValidationRecordRow.execution_id.is_(None),  # type: ignore[union-attr]
                )
                row = session.exec(stmt).first()
            if row is None:
                row = ValidationRecordRow(record_id=str(uuid.uuid4()), created_at=now)
            row.execution_id = record.execution_id
            row.watch_id = record.watch_id
            row.spec_id = record.spec_id
            row.project_id = record.project_id
            row.system = record.system
            row.objective = record.objective
            row.verdict = record.verdict
            row.confidence = record.confidence
            row.claimed_action = record.claimed_action
            row.expected = record.expected
            row.observed = record.observed
            row.check_marks_json = _marks_to_json(record.check_marks)
            row.evidence_refs_json = json.dumps(record.evidence_refs)
            row.message = record.message
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_by_execution(self, execution_id: str) -> ValidationRecordRow | None:
        self.ensure_tables()
        with get_session() as session:
            stmt = select(ValidationRecordRow).where(
                ValidationRecordRow.execution_id == execution_id
            )
            return session.exec(stmt).first()

    def list_by_project(self, project_id: str, limit: int = 100) -> list[ValidationRecordRow]:
        self.ensure_tables()
        with get_session() as session:
            stmt = (
                select(ValidationRecordRow)
                .where(ValidationRecordRow.project_id == project_id)
                .order_by(col(ValidationRecordRow.created_at).desc())
                .limit(max(1, min(limit, 200)))
            )
            return list(session.exec(stmt).all())

    def row_to_record(self, row: ValidationRecordRow) -> ValidationRecord:
        refs: dict[str, Any] = {}
        try:
            refs = json.loads(row.evidence_refs_json or "{}")
        except json.JSONDecodeError:
            refs = {}
        return ValidationRecord(
            execution_id=row.execution_id,
            watch_id=row.watch_id,
            spec_id=row.spec_id,
            project_id=row.project_id,
            system=row.system,
            objective=row.objective,
            verdict=row.verdict,  # type: ignore[arg-type]
            confidence=row.confidence,
            claimed_action=row.claimed_action,
            expected=row.expected,
            observed=row.observed,
            check_marks=_marks_from_json(row.check_marks_json),
            evidence_refs=refs,
            message=row.message,
            created_at=row.created_at,
        )

    def open_watch(
        self,
        *,
        delivery_key: str,
        system: str,
        project_id: str,
        expected_spec_ids: list[str],
        subject: str = "",
        deadline_seconds: int = 60,
    ) -> ResponseWatchRow:
        self.ensure_tables()
        now = datetime.now(timezone.utc)
        from datetime import timedelta

        deadline = now + timedelta(seconds=deadline_seconds)
        with get_session() as session:
            stmt = select(ResponseWatchRow).where(
                ResponseWatchRow.delivery_key == delivery_key,
                ResponseWatchRow.status == "open",
            )
            existing = session.exec(stmt).first()
            if existing:
                return existing
            row = ResponseWatchRow(
                watch_id=str(uuid.uuid4()),
                delivery_key=delivery_key,
                system=system,
                project_id=project_id,
                expected_spec_ids_json=json.dumps(expected_spec_ids),
                opened_at=now,
                deadline_at=deadline,
                status="open",
                subject=subject[:240],
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_watch(self, watch_id: str) -> ResponseWatchRow | None:
        self.ensure_tables()
        with get_session() as session:
            row = session.get(ResponseWatchRow, watch_id)
            if row is not None:
                session.expunge(row)
            return row

    def get_watch_by_delivery(self, delivery_key: str) -> ResponseWatchRow | None:
        self.ensure_tables()
        with get_session() as session:
            stmt = (
                select(ResponseWatchRow)
                .where(ResponseWatchRow.delivery_key == delivery_key)
                .order_by(col(ResponseWatchRow.opened_at).desc())
            )
            row = session.exec(stmt).first()
            if row is not None:
                session.expunge(row)
            return row

    def satisfy_watch(
        self,
        delivery_key: str,
        *,
        spec_id: str = "",
        skip_reason: str = "",
    ) -> ResponseWatchRow | None:
        self.ensure_tables()
        with get_session() as session:
            stmt = select(ResponseWatchRow).where(
                ResponseWatchRow.delivery_key == delivery_key,
                ResponseWatchRow.status == "open",
            )
            row = session.exec(stmt).first()
            if not row:
                return None
            row.status = "satisfied"
            row.satisfied_spec_id = spec_id
            row.skip_reason = skip_reason
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def mark_overdue_watches(self) -> list[ResponseWatchRow]:
        self.ensure_tables()
        now = datetime.now(timezone.utc)
        with get_session() as session:
            stmt = select(ResponseWatchRow).where(
                ResponseWatchRow.status == "open",
                ResponseWatchRow.deadline_at <= now,
            )
            rows = list(session.exec(stmt).all())
            ids = [row.watch_id for row in rows]
            for row in rows:
                row.status = "overdue"
                session.add(row)
            session.commit()
        if not ids:
            return []
        with get_session() as session:
            refreshed = list(
                session.exec(
                    select(ResponseWatchRow).where(
                        col(ResponseWatchRow.watch_id).in_(ids)
                    )
                ).all()
            )
            # Detach with loaded attributes for callers outside the session.
            for row in refreshed:
                session.expunge(row)
            return refreshed

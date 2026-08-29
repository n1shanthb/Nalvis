import json
from datetime import datetime, timezone
from typing import Any, Optional
import asyncio
from sqlmodel import Field, Session, SQLModel, col, select
from sqlmodel import update as sqlmodel_update

from aip.persistence.db import get_engine, get_session
import uuid

class ApprovalStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"

class ApprovalEventRow(SQLModel, table=True):
    __tablename__ = "guardrails_approval_request"

    id: str = Field(primary_key=True)
    execution_id: str = Field(index=True)
    agent_id: str = Field(index=True)
    project_id: str = Field(index=True)
    tool: str = Field(index=True)
    arguments_json: str = "{}"
    reason: str = ""
    status: str = Field(default=ApprovalStatus.PENDING, index=True)
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    expires_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Exact action binding hash
    action_hash: str = ""

def ensure_approval_tables() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

class ApprovalStore:
    def __init__(self):
        self._events: dict[str, asyncio.Event] = {}

    def ensure_tables(self):
        ensure_approval_tables()

    def create(
        self,
        agent_id: str,
        project_id: str,
        tool: str,
        arguments: dict[str, Any],
        reason: str,
        action_hash: str,
        execution_id: str | None = None,
    ) -> ApprovalEventRow:
        self.ensure_tables()
        row = ApprovalEventRow(
            id=str(uuid.uuid4()),
            execution_id=execution_id or str(uuid.uuid4()),  # allow caller to bind execution id
            agent_id=agent_id,
            project_id=project_id,
            tool=tool,
            arguments_json=json.dumps(arguments, sort_keys=True),
            reason=reason,
            action_hash=action_hash,
        )
        with get_session() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            
        self._events[row.id] = asyncio.Event()
        return row

    def get(self, approval_id: str) -> Optional[ApprovalEventRow]:
        self.ensure_tables()
        with get_session() as session:
            return session.get(ApprovalEventRow, approval_id)

    def list_pending(self) -> list[ApprovalEventRow]:
        self.ensure_tables()
        with get_session() as session:
            return list(session.exec(
                select(ApprovalEventRow)
                .where(ApprovalEventRow.status == ApprovalStatus.PENDING)
                .order_by(col(ApprovalEventRow.created_at).desc())
            ).all())

    def get_by_hash(self, execution_id: str, action_hash: str) -> list[ApprovalEventRow]:
        self.ensure_tables()
        with get_session() as session:
            return list(session.exec(
                select(ApprovalEventRow)
                .where(ApprovalEventRow.execution_id == execution_id)
                .where(ApprovalEventRow.action_hash == action_hash)
            ).all())

    def list_for_execution(self, execution_id: str) -> list[ApprovalEventRow]:
        self.ensure_tables()
        with get_session() as session:
            return list(
                session.exec(
                    select(ApprovalEventRow)
                    .where(ApprovalEventRow.execution_id == execution_id)
                    .order_by(col(ApprovalEventRow.created_at).desc())
                ).all()
            )

    # Removed unsafe update_status

    def transition_status(self, approval_id: str, expected_status: str | None, new_status: str) -> bool:
        """Atomically transition status from expected_status -> new_status.

        If expected_status is None, perform unconditional update.
        Returns True if a row was updated, False otherwise.
        """
        self.ensure_tables()
        now = datetime.now(timezone.utc)
        with get_session() as session:
            if expected_status is None:
                # unconditional
                stmt = sqlmodel_update(ApprovalEventRow).where(ApprovalEventRow.id == approval_id).values(status=new_status, resolved_at=now)
            else:
                stmt = sqlmodel_update(ApprovalEventRow).where(ApprovalEventRow.id == approval_id, ApprovalEventRow.status == expected_status).values(status=new_status, resolved_at=now)
            result = session.exec(stmt)
            # commit to persist
            session.commit()
            # SQLModel/SQLAlchemy result may expose rowcount
            try:
                updated = result.rowcount if hasattr(result, 'rowcount') else 0
            except Exception:
                updated = 0

        # Wake up waiting execution thread only if we moved it into a terminal/changed state
        if updated:
            evt = self._events.pop(approval_id, None)
            if evt:
                evt.set()
        return bool(updated)

    async def wait_for_resolution(self, approval_id: str, timeout_seconds: int = 55) -> Optional[str]:
        """Wait for the approval status to change from PENDING."""
        evt = self._events.get(approval_id)
        if not evt:
            # No in-memory waiter: this can happen after a process restart.
            # Treat a missing event as a lost execution and expire the approval
            # so callers get a consistent EXPIRED result rather than ambiguous PENDING.
            row = self.get(approval_id)
            if not row:
                return None
            if row.status == ApprovalStatus.PENDING:
                # Mark explicitly expired for clarity.
                self.transition_status(approval_id, ApprovalStatus.PENDING, ApprovalStatus.EXPIRED)
                return ApprovalStatus.EXPIRED
            return row.status
            
        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.transition_status(approval_id, ApprovalStatus.PENDING, ApprovalStatus.EXPIRED)
            return ApprovalStatus.EXPIRED
            
        row = self.get(approval_id)
        return row.status if row else None

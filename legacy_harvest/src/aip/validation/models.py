"""Validation layer contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["PASS", "FAIL", "PARTIAL", "NOT_APPLICABLE", "INSUFFICIENT_EVIDENCE", "ERROR"]
VerdictStatus = Literal["PASS", "FAIL", "PARTIAL", "REVIEW", "INSUFFICIENT_EVIDENCE", "ERROR"]


class CheckMarks(BaseModel):
    outcome: CheckStatus = "NOT_APPLICABLE"
    response_sla: CheckStatus = "NOT_APPLICABLE"
    guardrail_bypass: CheckStatus = "NOT_APPLICABLE"
    log_ok: CheckStatus = "PASS"


class ValidationRecord(BaseModel):
    execution_id: str | None = None
    watch_id: str | None = None
    spec_id: str = ""
    project_id: str = ""
    system: str = ""
    objective: str = ""
    verdict: VerdictStatus = "INSUFFICIENT_EVIDENCE"
    confidence: float = 0.0
    claimed_action: str = ""
    expected: str = ""
    observed: str = ""
    check_marks: CheckMarks = Field(default_factory=CheckMarks)
    evidence_refs: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    created_at: datetime | None = None

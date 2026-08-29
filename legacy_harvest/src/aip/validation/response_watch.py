"""60-second response SLA watches."""

from __future__ import annotations

import logging
import threading
from typing import Any

from aip.validation.models import CheckMarks, ValidationRecord
from aip.validation.store import ValidationStore

logger = logging.getLogger(__name__)
_SLA_SECONDS = 60
_timers: dict[str, threading.Timer] = {}


def _store() -> ValidationStore:
    from aip.app_context import ctx

    return ctx.validation


def open_response_watch(
    *,
    delivery_key: str,
    system: str,
    project_id: str,
    expected_spec_ids: list[str],
    subject: str = "",
) -> str:
    row = _store().open_watch(
        delivery_key=delivery_key,
        system=system,
        project_id=project_id or "",
        expected_spec_ids=expected_spec_ids,
        subject=subject,
        deadline_seconds=_SLA_SECONDS,
    )
    watch_id = row.watch_id
    if watch_id in _timers:
        _timers[watch_id].cancel()
    timer = threading.Timer(_SLA_SECONDS, _fire_overdue, args=[delivery_key])
    timer.daemon = True
    _timers[watch_id] = timer
    timer.start()
    return watch_id


def satisfy_response_watch(
    delivery_key: str,
    *,
    spec_id: str = "",
    skip_reason: str = "",
) -> None:
    row = _store().satisfy_watch(delivery_key, spec_id=spec_id, skip_reason=skip_reason)
    if row and row.watch_id in _timers:
        _timers.pop(row.watch_id, None)


def sla_mark_for_delivery(delivery_key: str) -> str:
    row = _store().get_watch_by_delivery(delivery_key)
    if not row:
        return "NOT_APPLICABLE"
    if row.status == "satisfied":
        return "PASS"
    if row.status == "overdue":
        return "FAIL"
    return "PASS"


def sweep_overdue_watches() -> None:
    for row in _store().mark_overdue_watches():
        _create_overdue_record(row)


def _fire_overdue(delivery_key: str) -> None:
    try:
        row = _store().get_watch_by_delivery(delivery_key)
        if not row or row.status != "open":
            return
        _store().mark_overdue_watches()
        row = _store().get_watch_by_delivery(delivery_key)
        if row and row.status == "overdue":
            _create_overdue_record(row)
    except Exception:  # noqa: BLE001
        logger.exception("validation SLA overdue failed delivery=%s", delivery_key)


def _create_overdue_record(row: Any) -> None:
    import json

    watch_id = str(getattr(row, "watch_id", "") or "")
    live = _store().get_watch(watch_id) if watch_id else None
    if live is None:
        live = row
    specs = json.loads(getattr(live, "expected_spec_ids_json", None) or "[]")
    record = ValidationRecord(
        watch_id=getattr(live, "watch_id", None),
        spec_id=str(specs[0] if specs else ""),
        project_id=str(getattr(live, "project_id", "") or ""),
        system=str(getattr(live, "system", "") or ""),
        objective="Respond to inbound event within 60 seconds",
        verdict="FAIL",
        confidence=1.0,
        claimed_action="agent_response",
        expected="Terminal run or intentional skip within 60s",
        observed="No response before deadline",
        check_marks=CheckMarks(
            outcome="NOT_APPLICABLE",
            response_sla="FAIL",
            guardrail_bypass="NOT_APPLICABLE",
            log_ok="PASS",
        ),
        evidence_refs={
            "delivery_key": getattr(live, "delivery_key", ""),
            "subject": getattr(live, "subject", ""),
        },
        message="Bound agent did not respond within 60s",
    )
    _store().upsert_record(record)

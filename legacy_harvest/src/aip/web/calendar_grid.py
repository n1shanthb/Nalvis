"""Month-grid helpers for the Google Calendar UI (framework-independent)."""

from __future__ import annotations

from calendar import monthcalendar
from datetime import date, datetime, timedelta, timezone
from typing import Any


def month_matrix(year: int, month: int) -> list[list[date]]:
    """Return a Mon–Sun matrix of dates for the month view (includes adjacent pads)."""
    weeks: list[list[date]] = []
    cal = monthcalendar(year, month)
    # First day of this month
    first_of_month = date(year, month, 1)
    # Find Monday of the week containing the 1st
    lead = first_of_month.weekday()  # Mon=0 … Sun=6
    cursor = first_of_month - timedelta(days=lead)
    for _ in cal:
        row: list[date] = []
        for _day in range(7):
            row.append(cursor)
            cursor += timedelta(days=1)
        weeks.append(row)
    return weeks


def visible_range(year: int, month: int) -> tuple[date, date]:
    """First/last dates shown on the month grid (including adjacent-month pads)."""
    matrix = month_matrix(year, month)
    return matrix[0][0], matrix[-1][-1]


def _parse_event_instant(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # All-day: YYYY-MM-DD
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    # Timed: ISO datetime
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date()
    except ValueError:
        return None


def _event_end_inclusive(raw: Any, start_d: date) -> date:
    """Google all-day end is exclusive; timed end may be same day."""
    if raw is None:
        return start_d
    text = str(raw).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            end_excl = date.fromisoformat(text)
            if end_excl > start_d:
                return end_excl - timedelta(days=1)
            return start_d
        except ValueError:
            return start_d
    end_d = _parse_event_instant(raw)
    return end_d or start_d


def events_by_day(
    events: list[dict[str, Any]],
    year: int,
    month: int,
) -> dict[date, list[dict[str, Any]]]:
    """Bucket events onto each overlapping day in the visible month grid."""
    first, last = visible_range(year, month)
    by_day: dict[date, list[dict[str, Any]]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        start_d = _parse_event_instant(event.get("start"))
        if start_d is None:
            continue
        end_d = _event_end_inclusive(event.get("end"), start_d)
        if end_d < start_d:
            end_d = start_d
        cursor = start_d
        while cursor <= end_d:
            if first <= cursor <= last:
                by_day.setdefault(cursor, []).append(event)
            cursor += timedelta(days=1)
            if cursor - start_d > timedelta(days=366):
                break
    for day_events in by_day.values():
        day_events.sort(key=lambda e: str(e.get("start") or ""))
    return by_day


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Shift calendar month by delta months."""
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def iso_bounds_for_grid(year: int, month: int) -> tuple[str, str]:
    """RFC3339 timeMin / timeMax covering the visible grid (UTC)."""
    first, last = visible_range(year, month)
    start = datetime(first.year, first.month, first.day, tzinfo=timezone.utc)
    end = datetime(last.year, last.month, last.day, 23, 59, 59, tzinfo=timezone.utc)
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )

"""Google Calendar native REST tools — list / create / update / freebusy."""

from __future__ import annotations

from typing import Any, Callable

import httpx

from aip.integrations.gmail_oauth import (
    clear_gmail_token_cache,
    gmail_configured,
    resolve_gmail_access_token,
)
from aip.tools.base import NativeTool

_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def calendar_configured() -> bool:
    """Calendar reuses the Gmail Google OAuth refresh token (add Calendar scopes)."""
    return gmail_configured()


class CalendarRestClient:
    """Thin Calendar REST client with OAuth refresh + single 401 retry."""

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    ) -> Any:
        token = resolve_gmail_access_token()
        if not token:
            return {"error": "Google OAuth credentials are not configured"}
        url = f"{_CALENDAR_API}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=60.0) as client:
            resp = client.request(
                method, url, headers=headers, json=json_body, params=params
            )
            if resp.status_code == 401:
                clear_gmail_token_cache()
                token = resolve_gmail_access_token(force_refresh=True)
                if not token:
                    return {"error": "Google OAuth refresh failed after 401"}
                headers = {"Authorization": f"Bearer {token}"}
                resp = client.request(
                    method, url, headers=headers, json=json_body, params=params
                )
            if resp.status_code >= 400:
                return {
                    "error": f"Calendar {resp.status_code}",
                    "detail": resp.text[:800],
                }
            if resp.status_code == 204 or not resp.content:
                return {"ok": True}
            return resp.json()


def _client_or_error() -> CalendarRestClient | dict[str, Any]:
    if not calendar_configured():
        return {"error": "Google OAuth credentials are not configured"}
    return CalendarRestClient()


def list_calendars(_input: dict[str, Any] | None = None) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    data = client.request("GET", "/users/me/calendarList")
    if isinstance(data, dict) and data.get("error"):
        return data
    items = data.get("items") if isinstance(data, dict) else None
    calendars = []
    if isinstance(items, list):
        for c in items:
            if not isinstance(c, dict):
                continue
            calendars.append(
                {
                    "id": c.get("id"),
                    "summary": c.get("summary"),
                    "primary": bool(c.get("primary")),
                    "access_role": c.get("accessRole"),
                    "time_zone": c.get("timeZone"),
                }
            )
    return {"ok": True, "calendars": calendars}


def list_events(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    calendar_id = str(input.get("calendar_id") or "primary").strip() or "primary"
    params: dict[str, Any] = {"singleEvents": True, "orderBy": "startTime"}
    if input.get("time_min"):
        params["timeMin"] = str(input["time_min"])
    if input.get("time_max"):
        params["timeMax"] = str(input["time_max"])
    max_results = input.get("max_results")
    if max_results is not None:
        params["maxResults"] = int(max_results)
    if input.get("query"):
        params["q"] = str(input["query"])
    from urllib.parse import quote

    data = client.request(
        "GET",
        f"/calendars/{quote(calendar_id, safe='')}/events",
        params=params,
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    items = data.get("items") if isinstance(data, dict) else None
    events = []
    if isinstance(items, list):
        for e in items:
            if not isinstance(e, dict):
                continue
            start = e.get("start") if isinstance(e.get("start"), dict) else {}
            end = e.get("end") if isinstance(e.get("end"), dict) else {}
            events.append(
                {
                    "id": e.get("id"),
                    "summary": e.get("summary"),
                    "html_link": e.get("htmlLink"),
                    "start": start.get("dateTime") or start.get("date"),
                    "end": end.get("dateTime") or end.get("date"),
                    "status": e.get("status"),
                    "location": e.get("location"),
                }
            )
    return {"ok": True, "calendar_id": calendar_id, "events": events}


def get_event(input: dict[str, Any]) -> dict[str, Any]:
    from urllib.parse import quote

    client = _client_or_error()
    if isinstance(client, dict):
        return client
    calendar_id = str(input.get("calendar_id") or "primary").strip() or "primary"
    event_id = str(input.get("event_id") or "").strip()
    if not event_id:
        return {"error": "event_id is required"}
    data = client.request(
        "GET",
        f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    return {"ok": True, "event": data}


def create_event(input: dict[str, Any]) -> dict[str, Any]:
    from urllib.parse import quote

    client = _client_or_error()
    if isinstance(client, dict):
        return client
    calendar_id = str(input.get("calendar_id") or "primary").strip() or "primary"
    summary = str(input.get("summary") or "").strip()
    start = str(input.get("start") or "").strip()
    end = str(input.get("end") or "").strip()
    if not summary or not start or not end:
        return {"error": "summary, start, and end are required"}
    body: dict[str, Any] = {
        "summary": summary,
        "start": _time_payload(start),
        "end": _time_payload(end),
    }
    if input.get("description"):
        body["description"] = str(input["description"])
    if input.get("location"):
        body["location"] = str(input["location"])
    attendees = input.get("attendees")
    if isinstance(attendees, list) and attendees:
        body["attendees"] = [{"email": str(a)} for a in attendees if a]
    data = client.request(
        "POST",
        f"/calendars/{quote(calendar_id, safe='')}/events",
        json_body=body,
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    return {
        "ok": True,
        "event_id": data.get("id") if isinstance(data, dict) else None,
        "html_link": data.get("htmlLink") if isinstance(data, dict) else None,
        "event": data,
    }


def update_event(input: dict[str, Any]) -> dict[str, Any]:
    from urllib.parse import quote

    client = _client_or_error()
    if isinstance(client, dict):
        return client
    calendar_id = str(input.get("calendar_id") or "primary").strip() or "primary"
    event_id = str(input.get("event_id") or "").strip()
    if not event_id:
        return {"error": "event_id is required"}
    patch: dict[str, Any] = {}
    if input.get("summary"):
        patch["summary"] = str(input["summary"])
    if input.get("description") is not None:
        patch["description"] = str(input["description"])
    if input.get("location") is not None:
        patch["location"] = str(input["location"])
    if input.get("start"):
        patch["start"] = _time_payload(str(input["start"]))
    if input.get("end"):
        patch["end"] = _time_payload(str(input["end"]))
    if not patch:
        return {"error": "No fields to update"}
    data = client.request(
        "PATCH",
        f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
        json_body=patch,
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    return {"ok": True, "event": data}


def delete_event(input: dict[str, Any]) -> dict[str, Any]:
    from urllib.parse import quote

    client = _client_or_error()
    if isinstance(client, dict):
        return client
    calendar_id = str(input.get("calendar_id") or "primary").strip() or "primary"
    event_id = str(input.get("event_id") or "").strip()
    if not event_id:
        return {"error": "event_id is required"}
    data = client.request(
        "DELETE",
        f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    return {"ok": True, "deleted": event_id, "calendar_id": calendar_id}


def get_freebusy(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    time_min = str(input.get("time_min") or "").strip()
    time_max = str(input.get("time_max") or "").strip()
    if not time_min or not time_max:
        return {"error": "time_min and time_max are required (RFC3339)"}
    calendar_ids = input.get("calendar_ids") or ["primary"]
    if not isinstance(calendar_ids, list):
        calendar_ids = [str(calendar_ids)]
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": str(c)} for c in calendar_ids],
    }
    data = client.request("POST", "/freeBusy", json_body=body)
    if isinstance(data, dict) and data.get("error"):
        return data
    return {"ok": True, "freebusy": data}


def _time_payload(value: str) -> dict[str, str]:
    """All-day if date-only (YYYY-MM-DD); otherwise dateTime."""
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return {"date": text}
    return {"dateTime": text}


def build_calendar_tools() -> list[tuple[NativeTool, list[str], bool]]:
    defs: list[
        tuple[
            str,
            str,
            dict[str, Any],
            Callable[[dict[str, Any]], dict[str, Any]],
            list[str],
            bool,
        ]
    ] = [
        (
            "list_calendars",
            "List Google calendars for the authenticated user.",
            {"type": "object", "properties": {}},
            list_calendars,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "list_events",
            "List events on a calendar (optional time_min/time_max/query).",
            {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "query": {"type": "string"},
                },
            },
            list_events,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "get_event",
            "Get a single calendar event by id.",
            {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "event_id": {"type": "string"},
                },
                "required": ["event_id"],
            },
            get_event,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "create_event",
            "Create a calendar event (summary, start, end as RFC3339 or YYYY-MM-DD).",
            {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "start", "end"],
            },
            create_event,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "update_event",
            "Patch fields on an existing calendar event.",
            {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "event_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["event_id"],
            },
            update_event,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "delete_event",
            "Delete a calendar event by id.",
            {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string"},
                    "event_id": {"type": "string"},
                },
                "required": ["event_id"],
            },
            delete_event,
            ["calendar", "scheduling"],
            True,
        ),
        (
            "get_freebusy",
            "Query free/busy for one or more calendars between time_min and time_max.",
            {
                "type": "object",
                "properties": {
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "calendar_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["time_min", "time_max"],
            },
            get_freebusy,
            ["calendar", "scheduling"],
            True,
        ),
    ]
    out: list[tuple[NativeTool, list[str], bool]] = []
    for name, desc, schema, fn, tags, requires_oauth in defs:
        out.append(
            (
                NativeTool(
                    name=name,
                    description=desc,
                    input_schema=schema,
                    output_schema={"type": "object"},
                    _executor=fn,
                ),
                tags,
                requires_oauth,
            )
        )
    return out

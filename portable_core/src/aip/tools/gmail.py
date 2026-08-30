"""Gmail native REST tools — fetch, search, send, reply (+ watch helpers)."""

from __future__ import annotations

import base64
import re
import time
from email.mime.text import MIMEText
from typing import Any, Callable
from urllib.parse import quote

import httpx

from aip.config import settings
from aip.integrations.gmail_oauth import (
    clear_gmail_token_cache,
    gmail_configured,
    resolve_gmail_access_token,
)
from aip.tools.base import NativeTool

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"

# In-memory watch state (portable; no DB store)
_WATCH_STATE: dict = {}


class _InMemoryWatchStore:
    def get(self) -> dict:
        return dict(_WATCH_STATE)

    def upsert(self, **kwargs) -> dict:
        _WATCH_STATE.update({k: v for k, v in kwargs.items() if v is not None})
        return dict(_WATCH_STATE)


_watch_store = _InMemoryWatchStore()


def _user() -> str:
    return (settings.gmail_user or "").strip()


def _normalize_email_body(text: str) -> str:
    """Convert LLM JSON-escaped newlines (literal \\n) into real line breaks."""
    body = (text or "").strip()
    if "\\n" in body or "\\t" in body:
        body = body.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    return body


class GmailRestClient:
    """Thin Gmail REST client with OAuth refresh + single 401 retry."""

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    ) -> Any:
        try:
            token = resolve_gmail_access_token()
        except RuntimeError as exc:
            return {"error": "gmail_oauth", "detail": str(exc)}
        if not token:
            return {"error": "Gmail OAuth credentials are not configured"}
        url = f"{_GMAIL_API}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=60.0) as client:
            resp = client.request(
                method, url, headers=headers, json=json_body, params=params
            )
            if resp.status_code == 401:
                clear_gmail_token_cache()
                try:
                    token = resolve_gmail_access_token(force_refresh=True)
                except RuntimeError as exc:
                    return {"error": "gmail_oauth", "detail": str(exc)}
                if not token:
                    return {"error": "Gmail OAuth refresh failed after 401"}
                headers = {"Authorization": f"Bearer {token}"}
                resp = client.request(
                    method, url, headers=headers, json=json_body, params=params
                )
            if resp.status_code >= 400:
                return {
                    "error": f"Gmail {resp.status_code}",
                    "detail": resp.text[:800],
                }
            if resp.status_code == 204 or not resp.content:
                return {"ok": True}
            return resp.json()


def _client_or_error() -> GmailRestClient | dict[str, Any]:
    if not gmail_configured():
        return {"error": "Gmail OAuth credentials are not configured"}
    return GmailRestClient()


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    headers = payload.get("headers") or []
    out: dict[str, str] = {}
    if isinstance(headers, list):
        for h in headers:
            if isinstance(h, dict) and h.get("name"):
                out[str(h["name"]).lower()] = str(h.get("value") or "")
    return out


def _decode_body_data(data: str) -> str:
    raw = data.replace("-", "+").replace("_", "/")
    pad = "=" * (-len(raw) % 4)
    try:
        return base64.b64decode(raw + pad).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def _extract_body(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    body = payload.get("body") or {}
    data = body.get("data") if isinstance(body, dict) else None
    if data:
        return _decode_body_data(str(data))
    parts = payload.get("parts") or []
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            mime = str(part.get("mimeType") or "")
            if mime.startswith("multipart/"):
                nested = _extract_body(part)
                if nested:
                    texts.append(nested)
            elif mime == "text/plain":
                part_body = part.get("body") or {}
                if isinstance(part_body, dict) and part_body.get("data"):
                    texts.append(_decode_body_data(str(part_body["data"])))
            elif mime == "text/html" and not texts:
                part_body = part.get("body") or {}
                if isinstance(part_body, dict) and part_body.get("data"):
                    html = _decode_body_data(str(part_body["data"]))
                    texts.append(re.sub(r"<[^>]+>", " ", html))
    return "\n".join(t for t in texts if t).strip()


def _walk_parts(
    payload: dict[str, Any], acc: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    acc = acc if acc is not None else []
    if not payload:
        return acc
    filename = str(payload.get("filename") or "")
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    att_id = body.get("attachmentId") if body else None
    if filename and att_id:
        acc.append(
            {
                "filename": filename,
                "mime_type": str(payload.get("mimeType") or ""),
                "attachment_id": str(att_id),
                "size": int(body.get("size") or 0),
            }
        )
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            _walk_parts(part, acc)
    return acc


def get_profile_history_id() -> str | None:
    client = _client_or_error()
    if isinstance(client, dict):
        return None
    user = quote(_user(), safe="")
    data = client.request("GET", f"/users/{user}/profile")
    if isinstance(data, dict) and data.get("historyId"):
        return str(data["historyId"])
    return None


def list_message_ids_since_history(
    start_history_id: str,
) -> tuple[list[str], str | None]:
    client = _client_or_error()
    if isinstance(client, dict):
        raise RuntimeError(
            f"Gmail history API error: {client.get('detail') or client.get('error')}"
        )
    if not start_history_id:
        return [], None
    user = quote(_user(), safe="")
    data = client.request(
        "GET",
        f"/users/{user}/history",
        params={
            "startHistoryId": start_history_id,
            "historyTypes": "messageAdded",
            "maxResults": 100,
        },
    )
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(
            f"Gmail history API error: {data.get('detail') or data.get('error')}"
        )
    ids: list[str] = []
    seen: set[str] = set()
    history = (data or {}).get("history") if isinstance(data, dict) else None
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict):
                continue
            for item in entry.get("messagesAdded") or []:
                if not isinstance(item, dict):
                    continue
                msg = item.get("message") or {}
                if isinstance(msg, dict) and msg.get("id"):
                    mid = str(msg["id"])
                    if mid not in seen:
                        seen.add(mid)
                        ids.append(mid)
    newest = None
    if isinstance(data, dict) and data.get("historyId"):
        newest = str(data["historyId"])
    return ids, newest


def start_gmail_watch(topic_name: str | None = None) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    topic = (topic_name or settings.gmail_pubsub_topic or "").strip()
    if not topic:
        return {"error": "GMAIL_PUBSUB_TOPIC is not configured"}
    labels = [
        x.strip()
        for x in (settings.gmail_watch_label_ids or "INBOX").split(",")
        if x.strip()
    ]
    user = quote(_user(), safe="")
    result = client.request(
        "POST",
        f"/users/{user}/watch",
        json_body={
            "topicName": topic,
            "labelIds": labels,
            "labelFilterBehavior": "include",
        },
    )
    if isinstance(result, dict) and result.get("error"):
        _watch_store.upsert(last_error=str(result.get("detail") or result["error"]))
        return result
    history_id = str((result or {}).get("historyId") or "")
    expiration = str((result or {}).get("expiration") or "")
    state = _watch_store.upsert(
        history_id=history_id,
        expiration_ms=expiration,
        topic_name=topic,
        last_error="",
    )
    return {"ok": True, "watch": state, "raw": result}


def renew_gmail_watch_if_needed(*, force: bool = False) -> dict[str, Any]:
    topic = (settings.gmail_pubsub_topic or "").strip()
    if not topic or not gmail_configured():
        return {"ok": False, "skipped": True, "reason": "not_configured"}
    state = _watch_store.get()
    if not force and state.get("expiration_ms"):
        try:
            exp = int(state["expiration_ms"])
            now_ms = int(time.time() * 1000)
            renew_ms = max(1, int(settings.gmail_watch_renew_hours)) * 3600 * 1000
            if exp - now_ms > renew_ms:
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "not_due",
                    "watch": state,
                }
        except ValueError:
            pass
    return start_gmail_watch(topic)


def fetch_email(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    message_id = str(input.get("message_id") or "").strip()
    if not message_id:
        from aip.guardrails.identity import get_gmail_run_context

        run_ctx = get_gmail_run_context() or {}
        message_id = str(run_ctx.get("message_id") or "").strip()
    if not message_id:
        return {"error": "message_id is required"}
    user = quote(_user(), safe="")
    data = client.request(
        "GET",
        f"/users/{user}/messages/{quote(message_id, safe='')}",
        params={"format": "full"},
    )
    if isinstance(data, dict) and data.get("error"):
        return data
    payload = (data or {}).get("payload") if isinstance(data, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    headers = _header_map(payload)
    attachments = _walk_parts(payload)
    return {
        "message_id": message_id,
        "thread_id": (data or {}).get("threadId") if isinstance(data, dict) else "",
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "rfc_message_id": headers.get("message-id", ""),
        "auto_submitted": headers.get("auto-submitted", ""),
        "snippet": (data or {}).get("snippet") if isinstance(data, dict) else "",
        "body": _extract_body(payload),
        "label_ids": (data or {}).get("labelIds") if isinstance(data, dict) else [],
        "attachments": attachments,
    }


def search_emails(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    query = str(input.get("query") or input.get("q") or "").strip()
    if not query:
        return {"error": "query is required"}
    max_results = int(input.get("max_results") or 10)
    max_results = max(1, min(max_results, 50))
    user = quote(_user(), safe="")
    listing = client.request(
        "GET",
        f"/users/{user}/messages",
        params={"q": query, "maxResults": max_results},
    )
    if isinstance(listing, dict) and listing.get("error"):
        return listing
    messages = (listing or {}).get("messages") if isinstance(listing, dict) else []
    results: list[dict[str, Any]] = []
    if isinstance(messages, list):
        for item in messages:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            mid = str(item["id"])
            meta = client.request(
                "GET",
                f"/users/{user}/messages/{quote(mid, safe='')}",
                params=[
                    ("format", "metadata"),
                    ("metadataHeaders", "From"),
                    ("metadataHeaders", "Subject"),
                    ("metadataHeaders", "Date"),
                ],
            )
            if isinstance(meta, dict) and meta.get("error"):
                results.append({"message_id": mid, "error": meta.get("error")})
                continue
            payload = (meta or {}).get("payload") if isinstance(meta, dict) else {}
            headers = _header_map(payload if isinstance(payload, dict) else {})
            results.append(
                {
                    "message_id": mid,
                    "thread_id": (meta or {}).get("threadId")
                    if isinstance(meta, dict)
                    else "",
                    "from": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "date": headers.get("date", ""),
                    "snippet": (meta or {}).get("snippet")
                    if isinstance(meta, dict)
                    else "",
                }
            )
    return {"ok": True, "query": query, "count": len(results), "messages": results}


def send_email(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    to = str(input.get("to") or "").strip()
    subject = str(input.get("subject") or "").strip()
    body = _normalize_email_body(str(input.get("body") or ""))
    if not to or not subject or not body:
        return {"error": "to, subject, and body are required"}
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["From"] = _user()
    mime["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    user = quote(_user(), safe="")
    result = client.request(
        "POST",
        f"/users/{user}/messages/send",
        json_body={"raw": raw},
    )
    if isinstance(result, dict) and result.get("error"):
        return result
    return {
        "ok": True,
        "message_id": result.get("id") if isinstance(result, dict) else None,
        "thread_id": result.get("threadId") if isinstance(result, dict) else None,
    }


def send_email_reply(input: dict[str, Any]) -> dict[str, Any]:
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    message_id = str(input.get("message_id") or "").strip()
    body = _normalize_email_body(str(input.get("body") or ""))
    if not message_id or not body:
        return {"error": "message_id and body are required"}
    original = fetch_email({"message_id": message_id})
    if original.get("error"):
        return original
    subject = str(original.get("subject") or "")
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    to = str(original.get("from") or "").strip()
    if not to:
        return {"error": "original message has no From address"}
    # Prefer RFC Message-ID for threading headers (not the Gmail API id).
    rfc_id = str(original.get("rfc_message_id") or "").strip() or message_id
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["From"] = _user()
    mime["Subject"] = subject
    mime["In-Reply-To"] = rfc_id
    mime["References"] = rfc_id
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    user = quote(_user(), safe="")
    payload: dict[str, Any] = {"raw": raw}
    thread_id = original.get("thread_id")
    if thread_id:
        payload["threadId"] = thread_id
    result = client.request(
        "POST",
        f"/users/{user}/messages/send",
        json_body=payload,
    )
    if isinstance(result, dict) and result.get("error"):
        return result
    return {
        "ok": True,
        "message_id": result.get("id") if isinstance(result, dict) else None,
        "thread_id": result.get("threadId") if isinstance(result, dict) else thread_id,
        "replied_to": message_id,
        "in_reply_to": rfc_id,
    }


def build_gmail_tools() -> list[tuple[NativeTool, list[str], bool]]:
    """Return (tool, tags, requires_gmail) for registry + CSP discovery."""
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
            "fetch_email",
            "Fetch a Gmail message by id. Returns from, subject, body, attachments.",
            {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
            fetch_email,
            ["gmail", "email"],
            True,
        ),
        (
            "search_emails",
            "Search Gmail with a Gmail query string (e.g. from:x subject:y newer_than:7d).",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
            search_emails,
            ["gmail", "email"],
            True,
        ),
        (
            "send_email_reply",
            "Send an in-thread reply to a Gmail message (uses RFC Message-ID when present).",
            {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["message_id", "body"],
            },
            send_email_reply,
            ["gmail", "email"],
            True,
        ),
        (
            "send_email",
            "Send a new email to an arbitrary address.",
            {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            send_email,
            ["gmail", "email"],
            True,
        ),
    ]
    out: list[tuple[NativeTool, list[str], bool]] = []
    for name, desc, schema, fn, tags, requires_gmail in defs:
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
                requires_gmail,
            )
        )
    return out

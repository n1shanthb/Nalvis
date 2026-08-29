"""Verify Gmail send/reply claims against the live mailbox."""

from __future__ import annotations

from typing import Any

from aip.tools.gmail import fetch_email, search_emails
from aip.validation.claims import bodies_match


def _is_transport_error(text: str) -> bool:
    low = (text or "").lower()
    return any(
        n in low
        for n in (
            "oauth",
            "timeout",
            "connection",
            "429",
            "500",
            "502",
            "503",
            "504",
            "unavailable",
            "not configured",
        )
    )


def _looks_sent(mail: dict[str, Any]) -> bool:
    labels = {str(x).upper() for x in (mail.get("label_ids") or [])}
    return "SENT" in labels


def _fetch_sent_candidate(claim: dict[str, Any]) -> dict[str, Any]:
    """Resolve the sent message the agent claimed — prefer send output id, then SENT search."""
    message_id = str(claim.get("message_id") or "").strip()
    body = str(claim.get("body") or "").strip()
    thread_id = str(claim.get("thread_id") or "").strip()
    replied_to = str(claim.get("replied_to") or "").strip()

    # Never treat the inbound replied-to id as the sent message.
    if message_id and message_id != replied_to:
        mail = fetch_email({"message_id": message_id})
        if not mail.get("error"):
            return mail

    # Fallback: find a recent SENT message in the same thread (or body match).
    query_parts = ["in:sent"]
    if thread_id:
        query_parts.append(f"thread:{thread_id}")
    listing = search_emails({"query": " ".join(query_parts), "max_results": 10})
    if listing.get("error"):
        return {"error": listing.get("error"), "detail": listing.get("detail")}
    for item in listing.get("messages") or []:
        mid = str(item.get("message_id") or "").strip()
        if not mid or mid == replied_to:
            continue
        mail = fetch_email({"message_id": mid})
        if mail.get("error"):
            continue
        if thread_id and str(mail.get("thread_id") or "") != thread_id:
            continue
        observed = str(mail.get("body") or mail.get("snippet") or "")
        if body and bodies_match(body, observed):
            return mail
        if not body:
            return mail
    if message_id:
        return fetch_email({"message_id": message_id})
    return {"error": "No SENT message found matching claim"}


def verify_gmail_send(claim: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    message_id = str(claim.get("message_id") or "").strip()
    body = str(claim.get("body") or "").strip()
    if not message_id and not body and not claim.get("thread_id"):
        return (
            "INSUFFICIENT_EVIDENCE",
            "Gmail message sent",
            "No message_id or body in tool output",
            {},
        )

    mail = _fetch_sent_candidate(claim)
    if mail.get("error"):
        err = str(mail.get("detail") or mail.get("error"))
        status = "ERROR" if _is_transport_error(err) else "FAIL"
        return (
            status,
            body[:120] or "send claimed",
            err,
            {"message_id": message_id},
        )

    observed_id = str(mail.get("message_id") or message_id)
    observed_body = str(mail.get("body") or mail.get("snippet") or "")
    refs = {
        "message_id": observed_id,
        "thread_id": mail.get("thread_id"),
        "label_ids": mail.get("label_ids") or [],
    }

    if not _looks_sent(mail):
        return (
            "FAIL",
            body[:120] or "send claimed",
            f"Message not in SENT ({mail.get('label_ids')})",
            refs,
        )
    if body and not bodies_match(body, observed_body):
        return "FAIL", body[:120], observed_body[:120], refs
    return "PASS", body[:120] or "send claimed", observed_body[:120] or "sent", refs

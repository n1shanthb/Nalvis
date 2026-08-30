"""Gmail OAuth refresh-token → access token (native REST Connected System)."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx

from aip.config import Settings

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_lock = Lock()
_cached_token: str | None = None
_cached_expires_at: float = 0.0


def _gmail_settings() -> Settings:
    """Re-read .env so GMAIL_* updates apply without a full process restart."""
    return Settings()


def gmail_configured() -> bool:
    s = _gmail_settings()
    return bool(
        (s.gmail_client_id or "").strip()
        and (s.gmail_client_secret or "").strip()
        and (s.gmail_refresh_token or "").strip()
        and (s.gmail_user or "").strip()
    )


def gmail_oauth_error(*, force_refresh: bool = False) -> str | None:
    """Return a user-facing OAuth error, or None when refresh succeeds."""
    if not gmail_configured():
        return "Gmail OAuth is not configured"
    try:
        token = resolve_gmail_access_token(force_refresh=force_refresh)
    except RuntimeError as exc:
        text = str(exc)
        if "invalid_grant" in text:
            return (
                "Gmail refresh token expired or revoked. "
                "Re-run scripts/google_oauth_consent.py and update GMAIL_REFRESH_TOKEN."
            )
        return text[:240] if text else "Gmail OAuth refresh failed"
    return None if token else "Gmail OAuth refresh returned no access token"


def resolve_gmail_access_token(*, force_refresh: bool = False) -> str | None:
    """Return a cached access token, refreshing from GMAIL_* env when needed."""
    if not gmail_configured():
        return None
    global _cached_token, _cached_expires_at
    now = time.time()
    with _lock:
        if (
            not force_refresh
            and _cached_token
            and now < (_cached_expires_at - 60)
        ):
            return _cached_token

    with httpx.Client(timeout=30.0) as client:
        s = _gmail_settings()
        resp = client.post(
            _TOKEN_URL,
            data={
                "client_id": (s.gmail_client_id or "").strip(),
                "client_secret": (s.gmail_client_secret or "").strip(),
                "refresh_token": (s.gmail_refresh_token or "").strip(),
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"OAuth token refresh failed: {resp.text[:400]}")
        data: dict[str, Any] = resp.json()
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("OAuth token refresh returned no access_token")
    expires_in = int(data.get("expires_in") or 3600)
    with _lock:
        _cached_token = token
        _cached_expires_at = time.time() + expires_in
    return token


def clear_gmail_token_cache() -> None:
    global _cached_token, _cached_expires_at
    with _lock:
        _cached_token = None
        _cached_expires_at = 0.0

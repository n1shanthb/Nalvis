#!/usr/bin/env python
"""Obtain a Google OAuth refresh token for Gmail + Calendar native connectors.

Google Cloud setup (one-time)
-----------------------------
1. Google Cloud Console → APIs & Services → Enable **Gmail API** and **Google Calendar API**.
2. OAuth consent screen → add your Google account as a test user (if app is in Testing).
3. Credentials → Create OAuth client ID:
   - Type: **Desktop app** (recommended), or Web application with redirect below.
4. Authorized redirect URI (Web clients only):
     http://127.0.0.1:8765/callback
5. Copy client ID + secret into `.env`:
     GMAIL_CLIENT_ID=...
     GMAIL_CLIENT_SECRET=...

Run
---
  python scripts/google_oauth_consent.py
  python scripts/google_oauth_consent.py --write-env    # patch .env automatically
  python scripts/google_oauth_consent.py --verify     # exchange + smoke-test Gmail API

Then restart API + worker so they pick up the new token.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Gmail read/send/watch + Calendar read/write (matches AgentSuite native tools).
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _load_settings() -> Any:
    from aip.config import Settings

    return Settings()


def _build_auth_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _exchange_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    if not data.get("refresh_token"):
        raise RuntimeError(
            "Google did not return a refresh_token. "
            "Revoke app access at https://myaccount.google.com/permissions "
            "and re-run with prompt=consent (this script already does)."
        )
    return data


def _fetch_user_email(access_token: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"userinfo failed ({resp.status_code}): {resp.text[:300]}")
    email = str(resp.json().get("email") or "").strip()
    if not email:
        raise RuntimeError("userinfo response had no email")
    return email


def _wait_for_callback(
    *,
    host: str,
    port: int,
    path: str,
    expected_state: str,
    timeout_sec: int,
) -> str:
    result: dict[str, str | None] = {"code": None, "error": None}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ARG002
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            qs = parse_qs(parsed.query)
            state = (qs.get("state") or [""])[0]
            if state != expected_state:
                result["error"] = "state mismatch (possible CSRF)"
                self._respond(400, "State mismatch. Close this tab and re-run the script.")
                done.set()
                return

            if "error" in qs:
                result["error"] = (qs.get("error") or ["unknown"])[0]
                desc = (qs.get("error_description") or [""])[0]
                self._respond(400, f"OAuth error: {result['error']} {desc}")
                done.set()
                return

            code = (qs.get("code") or [""])[0]
            if not code:
                result["error"] = "missing code"
                self._respond(400, "Missing authorization code.")
                done.set()
                return

            result["code"] = code
            self._respond(200, "Success — you can close this tab and return to the terminal.")
            done.set()

        def _respond(self, status: int, message: str) -> None:
            body = f"<html><body><h2>{message}</h2></body></html>".encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, port), Handler)
    server.timeout = 1.0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not done.wait(timeout=timeout_sec):
            raise TimeoutError(
                f"No OAuth callback within {timeout_sec}s. "
                f"Confirm redirect URI is registered: http://{host}:{port}{path}"
            )
        if result["error"]:
            raise RuntimeError(str(result["error"]))
        code = result.get("code")
        if not code:
            raise RuntimeError("OAuth callback missing code")
        return str(code)
    finally:
        server.shutdown()
        thread.join(timeout=3)


def _patch_env_file(env_path: Path, updates: dict[str, str]) -> None:
    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    lines = text.splitlines()
    remaining = dict(updates)
    out: list[str] = []
    seen: set[str] = set()

    key_re = re.compile(r"^([A-Z0-9_]+)\s*=")
    for line in lines:
        m = key_re.match(line)
        if m and m.group(1) in remaining:
            key = m.group(1)
            out.append(f"{key}={remaining.pop(key)}")
            seen.add(key)
        else:
            out.append(line)

    for key, value in remaining.items():
        if key not in seen:
            if out and out[-1].strip():
                out.append("")
            out.append(f"{key}={value}")

    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _verify_gmail_access(refresh_token: str, client_id: str, client_secret: str, user: str) -> None:
    with httpx.Client(timeout=30.0) as client:
        tok = client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if tok.status_code >= 400:
        raise RuntimeError(f"refresh_token verify failed: {tok.text[:400]}")
    access = str(tok.json().get("access_token") or "")
    profile_url = f"https://gmail.googleapis.com/gmail/v1/users/{user}/profile"
    with httpx.Client(timeout=30.0) as client:
        prof = client.get(profile_url, headers={"Authorization": f"Bearer {access}"})
    if prof.status_code >= 400:
        raise RuntimeError(f"Gmail profile check failed ({prof.status_code}): {prof.text[:300]}")
    data = prof.json()
    print(f"Gmail verify OK — mailbox: {data.get('emailAddress')} messages: {data.get('messagesTotal')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Google OAuth refresh token for Gmail + Calendar")
    parser.add_argument("--client-id", help="Override GMAIL_CLIENT_ID from .env")
    parser.add_argument("--client-secret", help="Override GMAIL_CLIENT_SECRET from .env")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/callback")
    parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for browser callback")
    parser.add_argument("--no-browser", action="store_true", help="Print URL only; do not open browser")
    parser.add_argument("--write-env", action="store_true", help="Write GMAIL_REFRESH_TOKEN + GMAIL_USER to .env")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--verify", action="store_true", help="Smoke-test refresh token against Gmail API")
    args = parser.parse_args()

    settings = _load_settings()
    client_id = (args.client_id or settings.gmail_client_id or "").strip()
    client_secret = (args.client_secret or settings.gmail_client_secret or "").strip()
    if not client_id or not client_secret:
        print(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env first "
            "(or pass --client-id / --client-secret).",
            file=sys.stderr,
        )
        return 1

    redirect_uri = f"http://{args.host}:{args.port}{args.path}"
    state = secrets.token_urlsafe(24)
    auth_url = _build_auth_url(client_id=client_id, redirect_uri=redirect_uri, state=state)

    print("Redirect URI (register in Google Cloud if using Web client):")
    print(f"  {redirect_uri}\n")
    print("Opening browser for Google consent…\n" if not args.no_browser else "Open this URL in your browser:\n")
    print(auth_url)
    print()

    if not args.no_browser:
        webbrowser.open(auth_url, new=1)

    try:
        code = _wait_for_callback(
            host=args.host,
            port=args.port,
            path=args.path,
            expected_state=state,
            timeout_sec=args.timeout,
        )
        token_data = _exchange_code(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"OAuth failed: {exc}", file=sys.stderr)
        return 1

    refresh_token = str(token_data.get("refresh_token") or "")
    access_token = str(token_data.get("access_token") or "")
    try:
        email = _fetch_user_email(access_token)
    except Exception:
        email = (settings.gmail_user or "").strip()

    print("\n--- Add to .env ---\n")
    print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
    if email:
        print(f"GMAIL_USER={email}")
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print()

    if args.write_env:
        env_path = Path(args.env_file)
        updates = {"GMAIL_REFRESH_TOKEN": refresh_token}
        if email:
            updates["GMAIL_USER"] = email
        if not settings.gmail_client_id:
            updates["GMAIL_CLIENT_ID"] = client_id
        if not settings.gmail_client_secret:
            updates["GMAIL_CLIENT_SECRET"] = client_secret
        _patch_env_file(env_path, updates)
        print(f"Updated {env_path}")

    if args.verify:
        if not email:
            print("--verify needs GMAIL_USER (from consent or .env)", file=sys.stderr)
            return 1
        try:
            _verify_gmail_access(refresh_token, client_id, client_secret, email)
        except Exception as exc:  # noqa: BLE001
            print(f"Verify failed: {exc}", file=sys.stderr)
            return 1

    print("Restart API + worker after updating .env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

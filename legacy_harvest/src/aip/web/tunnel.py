"""Local-dev Cloudflare quick tunnel for inbound webhooks (web layer only)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from typing import Any

from aip.config import settings

_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
_STATE_PATH = settings.generated_dir.parent / "tunnel_state.json"
_LOCAL_URL = "http://127.0.0.1:8000"

_lock = threading.Lock()
_process: subprocess.Popen[str] | None = None
_public_base = ""
_status = "stopped"
_error = ""
_url_changed = False
_reconnect_requested = False
_reconnect_force = False


def request_inbound_reconnect(*, force_watch: bool = False) -> None:
    """Signal inbound loop to reconnect (never run catch-up on the tunnel reader)."""
    global _reconnect_requested, _reconnect_force
    with _lock:
        _reconnect_requested = True
        _reconnect_force = _reconnect_force or force_watch


def take_inbound_reconnect_request() -> bool | None:
    """Return force_watch flag if a reconnect was requested, else None."""
    global _reconnect_requested, _reconnect_force
    with _lock:
        if not _reconnect_requested:
            return None
        force = _reconnect_force
        _reconnect_requested = False
        _reconnect_force = False
        return force


def _load_last_host() -> str:
    if not _STATE_PATH.is_file():
        return ""
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(raw, dict):
        return str(raw.get("hostname") or "").strip()
    return ""


def _save_last_host(hostname: str) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(
        json.dumps({"hostname": hostname}, indent=2),
        encoding="utf-8",
    )


def _binary() -> str | None:
    return shutil.which("cloudflared") or shutil.which("cloudflared.exe")


def webhook_urls(base: str) -> dict[str, str]:
    host = (base or "").rstrip("/")
    if not host:
        return {"github": "", "jira": "", "gmail": ""}
    return {
        "github": f"{host}/api/webhooks/github",
        "jira": f"{host}/api/webhooks/jira",
        "gmail": f"{host}/api/webhooks/gmail",
    }


def status() -> dict[str, Any]:
    with _lock:
        running = _process is not None and _process.poll() is None
        state = "running" if running and _public_base else (
            "error" if _error and not running else ("running" if running else "stopped")
        )
        if running and not _public_base:
            state = "starting"
        return {
            "status": state,
            "running": running,
            "binary": _binary() is not None,
            "public_base": _public_base,
            "urls": webhook_urls(_public_base),
            "url_changed": _url_changed,
            "error": _error,
            "install_hint": (
                None
                if _binary()
                else "Install cloudflared and ensure it is on PATH: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            ),
        }


def _reader(proc: subprocess.Popen[str]) -> None:
    global _public_base, _status, _error, _url_changed
    assert proc.stdout is not None
    last = _load_last_host()
    for line in proc.stdout:
        match = _URL_RE.search(line or "")
        if not match:
            continue
        url = match.group(0).rstrip("/")
        changed = False
        with _lock:
            _public_base = url
            _status = "running"
            _error = ""
            changed = bool(last) and last.rstrip("/") != url
            _url_changed = changed
            _save_last_host(url)
        last = url
        # Never run catch-up on the cloudflared reader thread.
        request_inbound_reconnect(force_watch=changed)


def start() -> dict[str, Any]:
    global _process, _public_base, _status, _error, _url_changed
    binary = _binary()
    if not binary:
        return status()
    with _lock:
        if _process is not None and _process.poll() is None:
            return status()
        _error = ""
        _public_base = ""
        _url_changed = False
        env = os.environ.copy()
        try:
            proc = subprocess.Popen(
                [binary, "tunnel", "--url", _LOCAL_URL, "--no-autoupdate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:  # noqa: BLE001
            _status = "error"
            _error = str(exc)
            return status()
        _process = proc
        _status = "starting"
        threading.Thread(target=_reader, args=(proc,), daemon=True).start()
    return status()


def stop() -> dict[str, Any]:
    global _process, _public_base, _status, _error
    with _lock:
        proc = _process
        _process = None
        _public_base = ""
        _status = "stopped"
        _error = ""
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()
    return status()

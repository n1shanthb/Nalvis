"""Cloudflare quick tunnel for inbound webhooks (control-plane web layer)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from typing import Any

from aip.config import generated_path, settings

_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
_STATE_PATH = generated_path() / "tunnel_state.json"
_LOCAL_URL = f"http://{settings.api_host}:{settings.api_port}"

_lock = threading.Lock()
_process: subprocess.Popen[str] | None = None
_public_base = ""
_status = "stopped"
_error = ""
_url_changed = False


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
        state = (
            "running"
            if running and _public_base
            else (
                "error"
                if _error and not running
                else ("running" if running else "stopped")
            )
        )
        if running and not _public_base:
            state = "starting"
        return {
            "status": state,
            "running": running,
            "binary": _binary() is not None,
            "public_base": _public_base,
            "local_url": _LOCAL_URL,
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
        with _lock:
            _public_base = url
            _status = "running"
            _error = ""
            _url_changed = bool(last) and last.rstrip("/") != url
            _save_last_host(url)
        last = url


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
        try:
            proc = subprocess.Popen(
                [binary, "tunnel", "--url", _LOCAL_URL, "--no-autoupdate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=os.environ.copy(),
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

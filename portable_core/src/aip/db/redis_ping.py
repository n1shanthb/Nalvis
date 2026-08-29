"""Redis connectivity helpers (cache / rate-limit / locks — not source of truth)."""

from __future__ import annotations

from typing import Any

from aip.config import settings


def check_redis() -> dict[str, Any]:
    try:
        import redis
    except ImportError as exc:
        return {"ok": False, "error": f"redis not installed: {exc}"}

    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3)
        pong = client.ping()
        info = client.info(section="server")
        return {
            "ok": bool(pong),
            "redis_version": info.get("redis_version"),
            "url_host": settings.redis_url.replace("redis://", "").split("/")[0],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}

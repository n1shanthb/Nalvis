"""Redis rate limits / short locks for connector writes (Authority data plane)."""

from __future__ import annotations

import time
from typing import Any

from aip.config import settings


def check_rate_limit(*, key: str, limit: int = 30, window_sec: int = 60) -> dict[str, Any]:
    """
    Simple fixed-window token counter in Redis.
    Returns {ok, remaining, error?}. Fail-open if Redis is down (log via error field).
    """
    try:
        import redis
    except ImportError:
        return {"ok": True, "remaining": limit, "error": "redis package missing — fail open"}

    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        bucket = f"rl:{key}:{int(time.time() // window_sec)}"
        count = client.incr(bucket)
        if count == 1:
            client.expire(bucket, window_sec + 1)
        remaining = max(0, limit - int(count))
        if count > limit:
            return {"ok": False, "remaining": 0, "error": f"rate limit exceeded for {key}"}
        return {"ok": True, "remaining": remaining}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "remaining": limit, "error": f"redis unavailable fail-open: {exc}"}

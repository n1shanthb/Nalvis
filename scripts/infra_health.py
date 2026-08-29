"""Check Postgres, Redis, and Temporal connectivity."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))


async def check_temporal() -> dict:
    from temporalio.client import Client

    from aip.config import settings

    try:
        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        # Lightweight call: get system info if available, else just connected
        return {
            "ok": True,
            "host": settings.temporal_host,
            "namespace": settings.temporal_namespace,
            "task_queue": settings.temporal_task_queue,
            "identity": getattr(client, "identity", None),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}


async def main() -> int:
    from aip.db.ping import check_postgres
    from aip.db.redis_ping import check_redis

    report = {
        "postgres": await check_postgres(),
        "redis": check_redis(),
        "temporal": await check_temporal(),
    }
    print(json.dumps(report, indent=2, default=str))
    ok = all(bool(v.get("ok")) for v in report.values())
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

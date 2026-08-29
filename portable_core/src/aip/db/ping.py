"""Postgres connectivity helpers (async + sync) for the app data plane."""

from __future__ import annotations

from typing import Any

from aip.config import settings


async def check_postgres() -> dict[str, Any]:
    try:
        import asyncpg
    except ImportError as exc:
        return {"ok": False, "error": f"asyncpg not installed: {exc}"}

    dsn = settings.database_url_sync.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=5)
        try:
            val = await conn.fetchval("SELECT 1")
            version = await conn.fetchval("SHOW server_version")
        finally:
            await conn.close()
        return {"ok": val == 1, "server_version": version, "database": "agentsuite"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}


def check_postgres_sync() -> dict[str, Any]:
    try:
        import asyncio

        return asyncio.run(check_postgres())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}

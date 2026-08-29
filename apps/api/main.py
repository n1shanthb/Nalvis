"""Agentsuite control-plane API — webhooks, tunnel, connector smoke."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from aip import __version__ as aip_version
from aip.connectors import smoke as connector_smoke
from apps.api import tunnel
from apps.api.deliveries import list_deliveries
from apps.api.webhooks_gmail import router as gmail_router
from apps.api.webhooks_github import router as github_router
from apps.api.webhooks_jira import router as jira_router

app = FastAPI(
    title="AgentSuite Control Plane",
    version="0.1.0",
    description="Webhooks + cloudflared tunnel + connector smoke for GitHub/Jira/Gmail/Calendar",
)

app.include_router(github_router)
app.include_router(jira_router)
app.include_router(gmail_router)


@app.get("/health")
def health() -> dict[str, Any]:
    from aip.db.ping import check_postgres_sync
    from aip.db.redis_ping import check_redis

    infra = {
        "postgres": check_postgres_sync(),
        "redis": check_redis(),
    }
    infra_ok = all(bool(v.get("ok")) for v in infra.values())
    return {
        "ok": True,
        "service": "agentsuite-api",
        "aip_version": aip_version,
        "infra": infra,
        "infra_ok": infra_ok,
        "connectors": connector_smoke.health_snapshot(),
    }


@app.get("/api/infra/health")
async def infra_health() -> dict[str, Any]:
    """Deep infra check including Temporal (Authority data/orchestration plane)."""
    from aip.config import settings
    from aip.db.ping import check_postgres
    from aip.db.redis_ping import check_redis

    temporal: dict[str, Any]
    try:
        from temporalio.client import Client

        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        temporal = {
            "ok": True,
            "host": settings.temporal_host,
            "namespace": settings.temporal_namespace,
            "task_queue": settings.temporal_task_queue,
            "identity": getattr(client, "identity", None),
        }
    except Exception as exc:  # noqa: BLE001
        temporal = {"ok": False, "error": str(exc)[:300]}

    report = {
        "postgres": await check_postgres(),
        "redis": check_redis(),
        "temporal": temporal,
    }
    return {
        "ok": all(bool(v.get("ok")) for v in report.values()),
        "services": report,
    }


@app.get("/api/tunnel")
def tunnel_status() -> dict[str, Any]:
    return tunnel.status()


@app.post("/api/tunnel/start")
def tunnel_start() -> dict[str, Any]:
    return tunnel.start()


@app.post("/api/tunnel/stop")
def tunnel_stop() -> dict[str, Any]:
    return tunnel.stop()


@app.get("/api/webhooks/deliveries")
def webhook_deliveries(limit: int = 50) -> dict[str, Any]:
    return {"deliveries": list_deliveries(limit=limit)}


@app.get("/api/connectors/health")
def connectors_health() -> dict[str, Any]:
    return connector_smoke.health_snapshot()


class SmokeRequest(BaseModel):
    systems: list[str] = Field(
        default_factory=lambda: ["github", "jira", "gmail", "calendar"]
    )
    dry_run: bool = False


@app.post("/api/connectors/smoke")
def connectors_smoke(body: SmokeRequest) -> dict[str, Any]:
    if body.dry_run:
        return {"ok": True, "dry_run": True, "health": connector_smoke.health_snapshot()}
    results: dict[str, Any] = {}
    wanted = {s.strip().lower() for s in body.systems}
    if "github" in wanted:
        results["github"] = connector_smoke.smoke_github()
    if "jira" in wanted:
        results["jira"] = connector_smoke.smoke_jira_mcp_create()
    if "gmail" in wanted:
        results["gmail"] = connector_smoke.smoke_gmail_send()
    if "calendar" in wanted:
        results["calendar"] = connector_smoke.smoke_calendar_create()
    return {"ok": all(bool(v.get("ok")) for v in results.values() if isinstance(v, dict)), "results": results}

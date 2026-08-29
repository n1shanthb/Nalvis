# Infra readiness evidence (Phase 0)

Authority alignment: Temporal + Postgres + Redis (Canonical architecture / Technology decisions).

## Verified locally
- `docker compose up -d` → postgres, redis, temporal, temporal-ui running
- `python scripts/infra_health.py` → OK (Postgres 16, Redis 7, Temporal `127.0.0.1:7233`)
- Temporal worker `python -m apps.worker.main` listening on `agentsuite-main`
- `python apps/worker/hello_runner.py` → `{"result": "hello, agentsuite"}` OK
- `GET /api/infra/health` → `ok: true` for all three services
- Domain schema tests: `Workspace` / `Run` / `Job` / `Evidence` / `ValidationOutcome` PASS

## Endpoints
- Temporal UI: http://localhost:8080
- Temporal gRPC: localhost:7233
- Postgres: localhost:5432 / db `agentsuite`
- Redis: localhost:6379

## Next (out of this goal)
- Single-tenant company bootstrap + KG graph ingest / workspace split
- Phase 1: CompanyRunWorkflow / ProductRunWorkflow / job lifecycle in Postgres

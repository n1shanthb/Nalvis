# Local infrastructure (Phase 0)

Authority alignment:
- Canonical architecture → Temporal, Postgres, Redis
- Technology decisions → Temporal + Postgres + Redis + FastAPI + OpenAI Agents SDK (runtime wired later)

## Start
```bash
docker compose up -d
docker compose ps
```

## Endpoints
| Service | URL / port |
|---------|------------|
| Temporal gRPC | `localhost:7233` |
| Temporal UI | http://localhost:8080 |
| Postgres (app DB `agentsuite`) | `localhost:5432` user/pass `agentsuite` |
| Redis | `localhost:6379` |

## Verify
```bash
python scripts/infra_health.py
python -m apps.worker.hello_runner
```

## Notes
- Temporal uses DBs `temporal` + `temporal_visibility` on the same Postgres.
- App schemas/migrations live under `portable_core` / future Alembic; do not use Temporal DBs for app data.

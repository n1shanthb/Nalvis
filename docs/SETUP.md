# Setup Guide

Get AgentSuite running locally with production-shaped infrastructure: Postgres, Redis, Temporal, API, worker, and frontend.

---

## Prerequisites

| Requirement | Version / notes |
|-------------|-----------------|
| **Docker** | For Postgres, Redis, Temporal |
| **Python** | 3.11+ |
| **Node.js** | 18+ (frontend) |
| **Git** | Clone and manage the repo |

Optional:

- **cloudflared** — public webhook tunnel for GitHub / Jira / Gmail inbound ([Integrations](http://localhost:5173/integrations) can start it from the UI)
- **OpenRouter or OpenAI API key** — Director routing and KG agent synthesis when not using stub LLM mode

---

## 1. Clone and configure environment

```powershell
cd e:\agentsuite
copy .env.example .env
```

Edit `.env` with your credentials. Minimum for a live spine:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` / `DATABASE_URL_SYNC` | Postgres (defaults match docker-compose) |
| `REDIS_URL` | Redis |
| `TEMPORAL_HOST` | Temporal gRPC (`127.0.0.1:7233`) |
| `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` | GitHub App writes |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_USER` | Gmail / Calendar |
| `OPENROUTER_API_KEY` or `OPENAI_API_KEY` | LLM (set `LLM_MODE=litellm` for live routing) |
| `SMOKE_GITHUB_OWNER`, `SMOKE_GITHUB_REPO`, `SMOKE_GITHUB_APP_REPO` | Smoke / App write targets |

Never commit `.env`. See `.env.example` for the full catalog.

Frontend env:

```powershell
cd frontend
copy .env.example .env
```

Set `VITE_API_MODE=http` so the console talks to the control plane API.

---

## 2. Start infrastructure

```powershell
cd e:\agentsuite
docker compose up -d
docker compose ps
```

| Service | Endpoint |
|---------|----------|
| Postgres (app DB) | `localhost:5432` — user/pass/db: `agentsuite` |
| Redis | `localhost:6379` |
| Temporal gRPC | `localhost:7233` |
| Temporal UI | http://localhost:8080 |

Verify connectivity:

```powershell
python scripts/infra_health.py
python -m apps.worker.hello_runner
```

---

## 3. Install Python dependencies

From repo root:

```powershell
pip install -e "./portable_core[dev]"
pip install -e ".[dev,agents]"
```

Both packages are required: **`portable_core`** is the domain engine (`aip.*`); **`agentsuite`** wraps `apps/api` and `apps/worker`.

Run tests:

```powershell
python -m pytest portable_core/tests apps/api/tests -q
```

---

## 4. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

---

## 5. Run application services

Use **three terminals** (all from repo root unless noted).

### Terminal 1 — Control plane API

```powershell
uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

### Terminal 2 — Temporal worker

```powershell
python -m apps.worker.main
```

Expected log line:

```
worker listening queue=agentsuite-main host=127.0.0.1:7233 ...
workflows=['CompanyRunWorkflow', 'ProductRunWorkflow', 'ValidationWorkflow', 'GmailInboundWorkflow', 'GithubInboundWorkflow']
```

Without the worker, runs stay queued and approvals never resume.

### Terminal 3 — Ops console

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173

---

## 6. First-use checklist

1. **Context Studio** (`/context`) — upload or paste KG JSON (e.g. `ex3.json`). Creates workspaces and agents.
2. **Integrations** (`/integrations`) — confirm connector health; start inbound tunnel if testing webhooks.
3. **Projects** — pick a workspace → Runs, Approvals, Agents, Validation.
4. **Smoke** (optional):

   ```powershell
   python scripts/smoke_connectors.py --health
   python scripts/ship_smoke.py
   ```

---

## 7. Inbound webhooks (optional)

With API running:

```powershell
curl -X POST http://127.0.0.1:8000/api/tunnel/start
curl http://127.0.0.1:8000/api/tunnel
```

Point GitHub App / Jira / Gmail Pub/Sub at the returned URLs. Tunnel URLs change on restart (quick tunnel) — update provider configs when `url_changed` is true.

Simulate Gmail without Pub/Sub:

```powershell
curl -X POST http://127.0.0.1:8000/api/webhooks/gmail/simulate -H "Content-Type: application/json" -d "{\"subject\":\"test\",\"from_addr\":\"you@example.com\"}"
```

---

## 8. Stop and reset

```powershell
docker compose down          # stop infra
docker compose down -v       # stop + delete volumes (fresh DB)
```

Clear demo state from UI: **Context Studio → Clear all data**, or `DELETE /api/demo/state`.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Runs stuck `queued` | Worker running? `python -m apps.worker.main` |
| Approvals empty after webhook | Hit **Refresh** on Approvals; console re-fetches on focus |
| GitHub writes fail scope error | `SMOKE_GITHUB_APP_REPO` must match App-installed repo |
| Gmail replies to wrong address | Deny stale HIL items; send fresh mail from external account to `GMAIL_USER` |
| `llm_configured()` false | Set `OPENROUTER_API_KEY` or `OPENAI_API_KEY`; restart worker |
| Temporal connection refused | `docker compose ps` — wait for postgres healthy, then temporal |

For architecture and design rationale, see [ARCHITECTURE.md](ARCHITECTURE.md).

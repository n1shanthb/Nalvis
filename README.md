# AgentSuite

**Single-tenant, multi-product agentic automation** for engineering and ops teams. Ingest a company knowledge graph, split work across product workspaces, and execute governed jobs on **GitHub, Jira, Gmail, and Calendar** — with durable orchestration, human-in-the-loop controls, and independent evidence validation.

This is an **operations console**, not a chatbot. Agents are specialized executors; every external write is policy-gated, auditable, and verified against live system state.

---

## At a glance

| Layer | Technology |
|-------|------------|
| Control plane | FastAPI |
| Orchestration | [Temporal](https://temporal.io/) |
| Agent runtime | OpenAI Agents SDK |
| Persistence | PostgreSQL |
| Cache / rate limits | Redis |
| Connectors | GitHub & Jira (MCP), Gmail & Calendar (native OAuth) |
| Frontend | React 19, Vite, TypeScript |

Runs survive process restarts. Workers scale horizontally. Writes never happen inside HTTP request handlers.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [**Setup guide**](docs/SETUP.md) | Prerequisites, infrastructure, env, running locally |
| [**Features & capabilities**](docs/FEATURES.md) | What the platform does — agents, integrations, governance, validation |
| [**Architecture**](docs/ARCHITECTURE.md) | System design, reliability patterns, scaling model |
| [**AUTHORITY.md**](AUTHORITY.md) | Authoritative scope and architecture contract |
| [**CONNECT.md**](CONNECT.md) | Connector smoke tests and webhook tunnel |
| [**PHASES.md**](PHASES.md) | Build phases and definition-of-done |

---

## Quick start

```bash
# 1. Infrastructure
docker compose up -d

# 2. Python (from repo root)
copy .env.example .env   # fill secrets
pip install -e "./portable_core[dev]"
pip install -e ".[dev,agents]"

# 3. Frontend
cd frontend && copy .env.example .env && npm install && cd ..

# 4. Run (three terminals)
uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
python -m apps.worker.main
cd frontend && npm run dev
```

Verify infra: `python scripts/infra_health.py`

Full details: [**docs/SETUP.md**](docs/SETUP.md)

---

## Repository layout

```
agentsuite/
├── apps/
│   ├── api/          # FastAPI control plane (routes, webhooks, tunnel)
│   └── worker/       # Temporal worker process
├── portable_core/    # Domain engine (aip.*): orchestration, connectors, DB, Director
├── frontend/         # Ops console (React)
├── infra/            # Postgres init, Temporal dynamic config
├── scripts/          # Smoke tests, health checks
└── docs/             # Setup, features, architecture
```

**`portable_core`** holds the execution engine — KG ingest, routing, jobs, evidence, validation. **`apps/`** are deployable entrypoints that import it.

---

## Core workflows

1. **Context Studio** — paste or upload company KG JSON → deterministic inventory + LLM agent synthesis → workspaces and agents persisted.
2. **Company run** — Temporal `CompanyRunWorkflow` fans out per product workspace; Director routes signals to specialist agents.
3. **Execute + validate** — workers perform real connector writes; Validation Agent re-fetches external state → `PASS` / `FAIL` / `NO_EVIDENCE`.
4. **HIL** — sensitive writes pause for human approve / deny / edit in the Approvals inbox; workflow resumes via Temporal signal.

Inbound **GitHub**, **Gmail**, and **Jira** webhooks start runs from live events (PR opened, mail received, etc.).

---

## License

Private / internal — see repository owner for terms.

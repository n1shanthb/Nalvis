# Architecture

How AgentSuite is built for **durable execution**, **independent verification**, and **horizontal scale** — without coupling long-running work to HTTP request lifetimes.

---

## System overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│  Ops console    │────▶│  Control plane   │────▶│  Temporal               │
│  (React/Vite)   │     │  (FastAPI)       │     │  CompanyRunWorkflow     │
└─────────────────┘     └────────┬─────────┘     │  ProductRunWorkflow     │
                                 │               │  GmailInboundWorkflow   │
                                 │               │  GithubInboundWorkflow  │
                                 ▼               └───────────┬─────────────┘
                        ┌──────────────────┐                 │
                        │  PostgreSQL      │◀────────────────┤
                        │  runs/jobs/HIL   │                 │
                        └──────────────────┘                 ▼
                        ┌──────────────────┐     ┌─────────────────────────┐
                        │  Redis           │◀────│  Execution workers      │
                        │  rate limits     │     │  (stateless, scalable)  │
                        └──────────────────┘     └───────────┬─────────────┘
                                                             │
                    ┌────────────────────────────────────────┼────────────────┐
                    ▼                    ▼                   ▼                ▼
              GitHub MCP           Jira MCP            Gmail REST      Calendar REST
              + GitHub App         (Atlassian)         (OAuth)         (OAuth)
```

Three planes:

| Plane | Role | Components |
|-------|------|------------|
| **Control** | Accept KG, start runs, serve status, webhook ingress | FastAPI, React console |
| **Execution** | Durable workflows, agent jobs, connector I/O | Temporal workers, OpenAI Agents SDK runtime |
| **Data** | Source of truth + coordination | PostgreSQL, Redis |

---

## Technology choices

| Concern | Choice | Why it matters here |
|---------|--------|---------------------|
| Workflow durability | **Temporal** | Run state survives crashes; retries, timeouts, and HIL signals are first-class |
| API surface | **FastAPI** | Typed request/response models; async-friendly; OpenAPI for control plane |
| Agent execution | **OpenAI Agents SDK** | Tool-bound specialists with structured I/O; LLM optional per path |
| Primary store | **PostgreSQL 16** | Runs, jobs, approvals, policies, agents, audit indexes — JSONB for flexible payloads |
| Coordination | **Redis 7** | Integration rate limits; optional locks; not source of truth |
| GitHub / Jira | **MCP** | Model Context Protocol tool surfaces + native REST helpers for evidence |
| Gmail / Calendar | **Native Google APIs** | OAuth refresh tokens; Pub/Sub watch for inbound |
| Frontend | **React 19 + Vite + TS** | Ops console; HttpAdapter to live API |
| Domain logic | **`portable_core` (`aip.*`)** | Testable engine separated from deployable entrypoints |

---

## Reliability patterns

These are structural — not optional add-ons.

### Durable orchestration

- Every company run is a **Temporal workflow** with a stable workflow ID (`company-run-{uuid}`).
- Child **ProductRunWorkflow** per workspace; fan-out / fan-in with aggregated status (`succeeded`, `partial`, `failed`).
- **Activities** wrap DB access and connector calls with retry policies tuned per operation (reads vs writes).

Long MCP or Google API calls **never** run inside FastAPI handlers. Webhooks enqueue work and return quickly.

### Idempotency

External write activities compute idempotency keys from `run_id + workspace_id + job_type + requested_action`. Retries do not duplicate issues, reviews, or emails.

### Human-in-the-loop as workflow pause

HIL is not a polling loop in the API. The workflow **waits on a Temporal signal** (`approval_decision`) after creating an approval row. Approve/deny from the console signals the workflow; execution continues exactly once.

### Evidence-first success

A job cannot succeed without satisfying its **evidence contract**. The Validation Agent independently re-queries GitHub, Gmail, Jira, or Calendar and returns:

- **PASS** — external state matches claim
- **FAIL** — contradiction or missing artifact
- **NO_EVIDENCE** — agent claimed success without verifiable fields

Failed executes also produce validation rows where applicable, so the Validation page reflects reality.

### Fail-closed routing

Director proposals pass through a **Routing Auditor**. Out-of-scope repos, unsupported agents, and job types without evidence contracts are rejected before job rows exist.

Inbound Gmail skips system senders (mailer-daemon, bounces, self-sent) to avoid reply loops.

### Anti-fake-data

The UI and API do not seed synthetic runs, agents, or validations. Integration health reflects real probe results. Unsupported KG systems get agent stubs with `status=unsupported`, not simulated writes.

---

## Scalability model

| Dimension | Approach |
|-----------|----------|
| **Workers** | Stateless Temporal workers; add processes/containers on `agentsuite-main` task queue |
| **API** | Stateless FastAPI; scale replicas behind load balancer |
| **Postgres** | Run/job indexes; JSONB payloads; Temporal uses separate DBs on same instance locally |
| **Concurrency** | Bounded fan-out per company run; Redis rate limits per integration family |
| **Inbound** | Webhook → short workflow → activity fetch → start company run; debounce on Gmail thread/delivery |

Workers do not hold workflow state — Temporal does. That separation is what allows replacing or adding workers without migrating run state.

---

## Code organization

```
portable_core/src/aip/
├── orchestration/    # Temporal workflows + activities
├── director/         # Router + routing auditor
├── kg/               # Inventory, synthesizer, persist
├── jobs/             # Execute + validate registries
├── db/               # ORM, repo, serializers
├── policy/           # HIL / allow / deny engine
├── evidence/         # Per-job-type contracts
├── integrations/     # GitHub App, Gmail OAuth
├── connectors/       # MCP clients, smoke paths
├── tools/            # Gmail, Calendar native REST
├── llm/              # OpenAI-compatible client (OpenRouter/OpenAI)
└── runtime/          # Agents SDK adapter

apps/
├── api/              # HTTP routes, webhooks, tunnel
└── worker/           # Temporal worker registration
```

**`apps/`** is thin on purpose: deploy API and worker independently while sharing one domain package.

---

## Key workflows

### CompanyRunWorkflow

1. Optional KG ingest activity
2. For each workspace: child ProductRunWorkflow
3. Aggregate results → mark run status

### ProductRunWorkflow

1. Director route activity → materialize jobs
2. Per job: policy evaluate → HIL if required → execute activity → validate activity
3. Return job results to parent

### Inbound (GitHub / Gmail)

1. Webhook receives event → start inbound workflow
2. Normalize/fetch signal activity
3. Start company run with signal + objectives
4. Director uses webhook facts before LLM

---

## Observability & audit

- **Run timeline** — queued, started, director notes, job transitions, validation events
- **Integration call log** — last successful call timestamps on Integrations page
- **Webhook deliveries** — received events with repo/action summary
- **Temporal UI** — workflow histories, activity failures, retries (localhost:8080 locally)

---

## Local vs production

Local development uses Docker Compose for Postgres, Redis, and Temporal — the same components referenced in [AUTHORITY.md](../AUTHORITY.md), not an in-memory substitute.

Production deployment adds:

- Managed Postgres and Redis
- Temporal Cloud or self-hosted Temporal cluster
- Secrets manager for OAuth and App keys
- Stable tunnel or public ingress for webhooks
- Multiple worker replicas and API instances

The application code path is the same; only infrastructure sizing and secrets delivery change.

---

## Further reading

- [AUTHORITY.md](../AUTHORITY.md) — authoritative contracts
- [portable_core/PORT_LEDGER.md](../portable_core/PORT_LEDGER.md) — legacy extraction boundary
- [PHASES.md](../PHASES.md) — build phases and DoD
- [CONNECT.md](../CONNECT.md) — live connector verification

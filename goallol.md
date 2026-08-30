# goallol.md — End-to-end execution goal

This file is the **active engineering goal** for making the ops console drive real work. It is subordinate to [`AUTHORITY.md`](AUTHORITY.md). If anything here conflicts with Authority, **Authority wins** and this file must be updated.

## Goal statement

Ship a **solid, non-mock spine** from Context Studio → persisted workspaces/agents → Temporal `CompanyRunWorkflow` → **real** external writes on **GitHub + Gmail + Calendar** (Jira nice-to-have) with evidence → independent Validation (`PASS` / `FAIL` / `NO_EVIDENCE`) → HIL approve/deny resume → Frontend pages showing **only** API/DB data (empty when empty).

Also: from ingested company context, **discover** automation agents for systems beyond v1 connectors (Slack, Notion, AWS, GCP, etc.), create them as first-class Agent records, and mark them **unsupported / inactive** until tools exist — then activate later without re-deriving identity.

## Authority references (must hold)

| Topic | Authority heading |
|---|---|
| Product + resume-ready outcomes | Product statement · End-result goals |
| Planes & locked stack | Canonical architecture · Technology decisions |
| Nouns | Domain model (Company, Workspace, Run, Job, Evidence, Validation) |
| Agent discovery vs execution | Multi-agent system design · Agent discovery vs agent execution |
| Facts vs meaning | LLM vs deterministic split (locked — anti-rules-engine) |
| Runnable v1 agents | Agent types (minimum executable set for v1) |
| Orchestration | Temporal orchestration (`CompanyRunWorkflow`, `ProductRunWorkflow`, `ValidationWorkflow`) |
| Governance | Human-in-the-loop (HIL) and policy engine |
| Proof | Evidence contracts · Observability & audit |
| UI contract + honesty | Frontend · Anti-fake-data rule |
| Change control | Change control (anti-drift rule) |

## Non-negotiables (anti-slop)

- **Concept over example (whole system):** examples in chat/docs are illustrations only. Build the underlying concept (general schemas, catalogs, workflows, auditors, contracts, interfaces). Never implement “for that example path” or only the demo story. Applies to Director, agents, HIL, validation, UI, connectors — everything.
- **No synthetic operational data** in UI (runs, agents-as-executed, approvals, validations, integration health).
- **No pretend Slack/Notion/AWS executors** — discovery yes, writes no, until connectors exist.
- **No long MCP/Google writes inside FastAPI request handlers** — Temporal activities only.
- **No “agent claimed success” without evidence fields**; ValidationAgent is read-only and authoritative for PASS.
- **Idempotency keys** on every external write activity.
- **Bounded concurrency** (per workspace + per integration) + Redis rate limits.
- Frontend product path: `HttpAdapter` → control plane; local empty store is not the product.

## Executable vs discovered agents

### v1 executable (tools available)

Only these external systems can run jobs today:

1. **GitHub** (MCP + App)
2. **Jira** (Atlassian MCP)
3. **Gmail** (native OAuth)
4. **Calendar** (native OAuth)
5. **ValidationAgent** (read-only across the above)

Runnable specializations follow Authority (Issue manager, PR reviewer, CI/CD, Jira sync, Gmail comms, Calendar scheduler, Validation).

### Discovered but unsupported (create agent, do not execute)

If KG/context implies automation involving e.g. **Slack, Notion, AWS, GCP, Linear, HubSpot**, …:

- Create an **Agent** row with mission, origin evidence (KG paths/signals), desired tool surface.
- Set status to **`unsupported`** (blocked: missing connector).
- **No write tools**; UI shows “Not supported — connect {system} to activate”.
- When that connector is later added under Authority change control, **activate** the same agent (attach tools + policies), do not silently invent a duplicate.

## Target architecture (engineering spine)

```text
Frontend (ops console)
  → FastAPI control plane (ingest, CRUD, start run, approve signal, queries)
  → Temporal: CompanyRunWorkflow → ProductRunWorkflow(s) → ValidationWorkflow
  → Workers/Activities: KG parse · agent synthesis+audit · ExecuteJob · validate
  → Postgres (SoT) · Redis (rate limit / short locks)
  → GitHub/Jira MCP · Gmail/Calendar native
```

### How agents / inventory are created (LLM vs deterministic)

**Deterministic (facts — not a semantic rules engine):**
1. Validate KG schema.
2. Build inventory: what exists, who owns it, evidence pointers (KG paths/doc ids), valid scopes, which systems are actually available vs merely named.

**LLM (meaning / capability):**
3. Propose what the work means, what capabilities it represents, what automation could help, and what agent specializations make sense (including `unsupported` for unavailable systems).

**Deterministic auditor (groundedness):**
4. Accept/reject proposals against inventory + availability + allowlists + evidence contracts.
5. Persist accepted workspaces, agents, and synthesized guardrails; operators may add guardrails later.

### How agents execute

0. **DirectorAgent (router)** selects specialists from the **live catalog + signal/objective**, for **any** scenario — not hardcoded example paths (mail≠always Gmail+GitHub; meeting≠always Calendar-only code branch).
1. Routing Auditor accepts/rejects the Director’s job list (no unsupported agents, in-scope only, evidence contract exists).
2. Run materializes Jobs with `job_type`, `requested_action`, `idempotency_key`, `agent_id`.
3. `ExecuteJobActivity`: policy + guardrail → deny / HIL wait / allow.
4. OpenAI Agents SDK runs with least-privilege wrapped tools.
5. Map connector response → Evidence contract fields; audit log.
6. ValidationWorkflow re-queries externally → PASS / FAIL / NO_EVIDENCE.

### Anti-example-coding (locked — whole goal)

Chat/docs examples are illustrations only. Forbidden anywhere in the spine:

- Coding only the narrated case (mail complaint, one smoke repo, one product name)
- `if complaint → github` / keyword trees that encode the demo story
- UI or API shapes that only work for a single happy path

Required: general Director + auditor + policy + evidence contracts + Temporal job lifecycle that stay valid when the scenario, channel, agent set, or company changes.

### Retries, concurrency, reliability

- Transient errors: Temporal activity retries with exponential backoff + jitter.
- Auth/scope 4xx: non-retryable job failure.
- HIL: workflow waits on signal; API `POST /approvals/{id}/decide` signals Temporal.
- Cap concurrent activities per workspace and per integration; Redis token buckets for quotas.
- Deterministic Temporal workflow IDs per `run_id` to prevent duplicate company runs.
- Director runs **once per planning step** (not once per idle agent); keeps fan-out small on purpose.

## Definition of done (this goal)

Verifiable, real, UI-visible:

1. **Ingest** real KG via Context Studio → workspaces persisted; executable agents created where GitHub/Jira/Gmail/Calendar scopes exist; any Slack/Notion/AWS/GCP-like signals become **unsupported** agents in Agents UI.
2. **Start Run** via API/UI → Temporal workflow ID stored; Jobs appear in Runs (not invented client-side).
3. **Director routing**: a signal/objective activates only the selected specialist(s), via **general catalog routing** (not example-specific if-branches); not every agent with overlapping connector access.
4. **Real writes required for DoD:** GitHub + Gmail + Calendar each leave evidence IDs/URLs in DB. **Jira is nice-to-have** — not required to close this goal.
5. **Validation** rows for those jobs are PASS or FAIL or NO_EVIDENCE from re-fetch — never auto-PASS from agent claim.
6. **One HIL path**: gated job → Approvals inbox → approve/deny → workflow resumes; audit immutable.
7. **Integrations** page shows live connector health/config from API (no fake cards).
8. Empty company / no runs ⇒ honest empty states.

## Explicit non-goals for this goal slice

- Multi-tenant SaaS.
- Chat UI.
- Implementing Slack/Notion/AWS/GCP connectors (discovery + unsupported agents only).
- **Jira as a DoD blocker** (connector remains in Authority v1; for *this* goal smoke it is optional).
- Perfect horizontal scale tuning (bounds + retries required; deep SRE polish can follow).

## Suggested first external writes (locked for this goal)

**Must prove real writes (smoke / spine DoD):**

1. **GitHub** (MCP/App) — issue or equivalent evidence-bearing write on the configured smoke repo only  
2. **Gmail** (native OAuth) — real send/draft path with `message_id` / `thread_id` evidence  
3. **Calendar** (native OAuth) — real create/update event with `calendar_id` / `event_id` evidence  

**Nice to have (not blocking this goal):**

- **Jira** (Atlassian MCP) — ticket create/transition with evidence; include if credentials/time allow, otherwise defer without failing the goal

Still: no fake success; ValidationAgent re-fetches evidence for whatever writes we claim.

## Build sequence (no glue)

1. Postgres persistence + control-plane read APIs so UI stops being empty for the wrong reasons.
2. `CompanyRunWorkflow` / job lifecycle in Temporal (states real in DB).
3. HIL signal ↔ Approvals API/UI.
4. Real write activities + evidence for **GitHub**, then **Gmail**, then **Calendar** (same ExecuteJob/evidence patterns — not three one-off scripts).
5. `ValidationWorkflow` for those job types.
6. **Jira** write path if time/credentials allow (non-blocking).
7. KG ingest → workspace + agent synthesis (executable + unsupported discovery).
8. Wire frontend `HttpAdapter` for all Authority pages on this spine.

## Risk & Authority guardrails

| Risk | Guardrail |
|---|---|
| Fake Slack “success” | Unsupported agents cannot run write activities |
| LLM invents repos / systems | Auditor vs deterministic inventory + availability |
| Deterministic semantic rules engine | Authority LLM vs deterministic split — facts only in code |
| Double create on retry | Idempotency keys + deterministic workflow IDs |
| UI looks “full” with lies | Anti-fake-data rule |
| Scope creep connectors | Authority non-goals + change control |

## Status

- **Goal owner:** **closed** (spine DoD met). Active follow-on: [`goalship.md`](goalship.md) (ship-ready Authority v1).
- **Authority version:** see `AUTHORITY.md` (Agent discovery vs agent execution; Agent runtime = OpenAI Agents SDK)
- **Phase map:** aligns with `PHASES.md` Phase 1→3 spine, plus discovery-of-unsupported agents at ingest
- **Verified live DoD smoke (2026-08-29):** run `7af48b77-f1cf-41b2-903b-e46d334cc2df` — GitHub issue #8 + Gmail `message_id`/`thread_id` + Calendar `event_id` all succeeded; validations **PASS** for all three; HIL approve on `gmail.send_email` (`appr-0f7f70ebd999`). Proof: `data/smoke_proof/latest.json` / `dod_smoke_20260829T162417Z.json`. Script: `scripts/dod_live_smoke.py`.
- **Agents SDK:** Authority locks runtime to OpenAI Agents SDK. ExecuteJob now goes through `aip.runtime.agents_sdk.execute_job_via_agents_runtime` (tools wrap portable_core connectors + evidence contracts). With `OPENAI_API_KEY` unset, the same SDK tool path is invoked directly (no LLM planner) — not a bypass of connectors/contracts. Optional LLM Runner activates when key is set.
- **Deferred to goalship:** OpenRouter wiring, inbound Gmail→run, rich KG aliases, Jira-required, GitHub PR/CI depth, Calendar update, cross-system path, Integrations lastSuccessfulCall, console-only ship smoke

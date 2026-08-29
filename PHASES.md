## Build Phases (0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8)

This document splits the system into **incremental phases** so we can plan, implement, and verify one slice at a time without drifting from `AUTHORITY.md`.

## Ground rules (anti-slop)
- **One phase at a time**: do not start the next phase until the current phase’s definition-of-done is met.
- **Authority-first**: if a phase requires scope/semantics changes, update `AUTHORITY.md` in the same change-set.
- **Plan → Build → Audit loop** per phase:
  - plan using `authority-anchored-planning`
  - implement
  - close gaps using `plan-vs-implementation-audit`

---

## Phase 0A — Reuse harvest from the previous codebase (reduce rewrites)
### Goal
Systematically port the **good, working modules** from the previous project (where GitHub/Jira MCP + native Gmail/Calendar already work) into this clean rebuild, without importing legacy orchestration patterns.

### Deliverables (as implemented)
- Quarantine: `legacy_harvest/` (reference only)
- Portable extract: `portable_core/` — see `portable_core/PORT_LEDGER.md`
- **Accepted cores**: contracts, guardrail engine/models, validation claims + rewrites, webhook inventories/match, in-memory catalog/bind
- **Connectors**: GitHub MCP provider, Jira seed MCP provider, native Gmail/Calendar tools + OAuth helpers
- **Boundary gates**: reject `app_context` / `inbound` / `persistence` / FastAPI routers / Temporal-less worker loops
- **Verdict mapping**: legacy → `PASS` / `FAIL` / `NO_EVIDENCE` (`aip.validation.verdicts`)
- Contract tests: `portable_core/tests/test_portable_core.py`

### Definition of done
- `portable_core` imports without forbidden legacy modules (static scan in tests).
- Verdict taxonomy normalized to PASS / FAIL / NO_EVIDENCE.
- `PORT_LEDGER.md` documents accept / reject / rewrite.

### Demo
- “Run portable_core contract tests; show PORT_LEDGER accept/reject lists.”

## Phase 0 — Repo scaffold + contracts (foundation)
### Goal
Create a minimal but “production-shaped” skeleton with **clear contracts** (jobs, evidence, validation outcomes) and environment wiring.

### Deliverables
- **Project skeleton**: API service, worker service, shared packages/modules layout.
- **Config system**: settings for Postgres/Redis/Temporal/MCP endpoints; env-based profiles.
- **Core domain schemas** (Pydantic):
  - `Workspace`, `Run`, `Job`, `Evidence`, `ValidationOutcome`
- **Authority alignment**: ensure `AUTHORITY.md` and naming conventions match the code structure.

### Definition of done
- A hello-world API endpoint returns service info + version.
- A hello-world Temporal worker connects to Temporal and can run a no-op workflow.
- Schemas compile and can serialize/deserialize sample objects.

### Demo
- “Start API + Worker; trigger a dummy run; observe run status.”

---

## Phase 1 — Temporal control plane + job lifecycle (durable execution)
### Goal
Implement the **durable orchestration layer** (Temporal workflows + activities) and job lifecycle storage.

### Deliverables
- Temporal workflows (authoritative names from `AUTHORITY.md`):
  - `CompanyRunWorkflow`
  - `ProductRunWorkflow`
  - `ValidationWorkflow` (stubbed validation allowed in Phase 1)
- **Job lifecycle** persisted in Postgres:
  - state transitions: queued → running → succeeded/failed/blocked_for_approval
  - audit events for transitions
- **Policy/HIL skeleton**:
  - dynamic policy read path (DB-backed)
  - workflow can pause for approval (signals) even if UI is not built yet
- **Idempotency framework**:
  - idempotency key generation for write activities (even if the writes are mocked here)

### Definition of done
- A run can be created and orchestrated end-to-end with multiple jobs per workspace.
- Workflow can block on an approval and resume via a manual API call (temporary endpoint ok).
- Postgres reflects job states + audit trail.

### Demo
- “Kick off a run that generates N jobs, blocks one for approval, resumes, and completes.”

---

## Phase 2 — OpenAI Agents runtime + policy/HIL plumbing (no MCP writes yet)
### Goal
Wire the **OpenAI Agents SDK runtime**, tool/agent scaffolding, and **policy/HIL gating** semantics end-to-end, while still using stub tools so we can validate governance and orchestration before touching real integrations.

### Deliverables
- OpenAI Agents SDK integration:
  - agent factory per workspace (scoped tools)
  - specialized agents (minimum set from `AUTHORITY.md`)
- Tool scaffolding and guardrails:
  - workspace-scoped tool registry (deny cross-workspace access by construction)
  - tool input/output guardrails placeholders (schema-first)
  - rate limiting and retries hooks (wired, may be no-op until MCP phases)
- Policy engine (DB-backed) and HIL:
  - dynamic per-action policy evaluation
  - workflow pause/resume for approvals via signals
  - separate `auto_merge_enabled` vs `hil_required` toggles in data model
- Evidence contract schemas (Pydantic) for all v1 job types (even if not yet produced by real MCP calls)

### Definition of done
- A workspace run can execute stubbed jobs through agents and:
  - block on HIL-gated actions and resume correctly
  - emit “claimed evidence” objects that are schema-valid
- Validation semantics are enforced at the contract level:
  - missing evidence → NO_EVIDENCE (not PASS)
  - contradictory evidence shape → FAIL (schema/guardrail tripwire)

### Demo
- “End-to-end run with agents + approvals + contract validation, using stub tools (no external side effects).”

---

## Phase 3 — GitHub MCP integration (real work + evidence + validation)
### Goal
Ship the first real integration with full “YC-level” semantics: scoped tools, policy gating, evidence production, and independent validation.

### Deliverables
- GitHub MCP tool wrappers (workspace-scoped):
  - read tools (list repos/PRs/issues, fetch PR details, etc.)
  - write tools (create issue, comment/review PR, label/assign) with policy/HIL gates
  - retries/timeouts + Redis rate limiting at tool boundary
- Evidence production for GitHub job types (from `AUTHORITY.md`)
- Validation checks for GitHub evidence (read-only re-query)

### Definition of done
- At least 2 GitHub job types execute real actions and validate to PASS with evidence links/IDs.
- A “fake success” without evidence becomes FAIL/NO_EVIDENCE.

### Demo
- “Create/triage an issue and review/comment on a PR, then validate evidence independently.”

---

## Phase 4 — Jira MCP integration (real work + evidence + validation)
### Goal
Add Jira execution with the same governance + evidence + validation guarantees.

### Deliverables
- Jira MCP tool wrappers (workspace-scoped), policy/HIL gating for writes
- Evidence contracts implemented for Jira job types
- Validator checks that re-query Jira to confirm state changes

### Definition of done
- At least 1 Jira ticket create or transition job validates to PASS with evidence.

### Demo
- “Create and/or transition a Jira ticket linked to a GitHub artifact, then validate.”

---

## Phase 5 — Gmail native integration (real work + evidence + validation)
### Goal
Add Gmail execution (draft/send/label/triage) with strict governance for external send.

### Deliverables
- Gmail native tool wrappers (workspace-scoped):
  - safe read operations (search threads, fetch message metadata)
  - write operations (draft, send, label) with policy/HIL gates (esp. external)
- Evidence contracts for `gmail.send_email`
- Validator checks (message/thread existence)

### Definition of done
- At least 1 “send email” or “draft + approve + send” flow validates to PASS with message/thread evidence.

### Demo
- “Draft an email, require approval, send, then validate message/thread IDs.”

---

## Phase 6 — Calendar native integration (real work + evidence + validation)
### Goal
Add scheduling/rescheduling with explicit HIL for high-risk actions (e.g., exec reschedules).

### Deliverables
- Calendar native tool wrappers (workspace-scoped) with policy/HIL gating
- Evidence contracts for create/update event
- Validator checks (event exists, times updated, attendees as expected)

### Definition of done
- At least 1 create-event and 1 update-event flow validates to PASS with event evidence.

### Demo
- “Create a meeting, then update/reschedule with approval if gated, then validate event IDs.”

---

## Phase 7 — Unified validation + cross-system workflows (hard mode)
### Goal
Make validation and orchestration feel “platform-level” across systems and products.

### Deliverables
- Standardized validation pipeline for all job types:
  - PASS / FAIL / NO_EVIDENCE persisted with evidence links and validator checks
- Cross-system workflows (examples; keep minimal):
  - GitHub issue ↔ Jira ticket linking/sync (status/refs)
  - Gmail triage → Jira ticket creation (with approval if external)
  - Calendar scheduling triggered by Jira/GitHub events (policy-gated)

### Definition of done
- At least one cross-system workflow runs end-to-end and every step validates.

### Demo
- “Email → Jira ticket → GitHub link → calendar meeting; validation shows PASS chain.”

---

## Phase 8 — Frontend ops console + analytics (resume polish)
### Goal
Ship the **operations console** UI and the “engineering maturity” surfaces: approvals inbox, validation reports, and agent success metrics.

### Deliverables
- Frontend pages (from `AUTHORITY.md`):
  - KG upload / workspace preview
  - runs list + run detail (timeline/DAG)
  - approvals inbox (approve/deny/edit)
  - policies editor (dynamic toggles; separate auto-merge toggle)
  - integrations health
  - validation reports
  - **agents directory + agent profiles** (run history + PASS/FAIL/NO_EVIDENCE success rate breakdowns)
- Observability surfaces:
  - run timeline from audit events
  - link out to evidence URLs/IDs

### Definition of done
- You can run the whole system from the UI without touching the CLI:
  - upload KG → preview workspaces → start run → approve gated actions → view validation outcomes
- Agents page shows:
  - per-agent run history
  - validation-driven success rate overall and by job type/workspace

### Demo
- “Full end-to-end run driven from UI with at least one approval and one validation PASS.”

---

## Phase selection guidance (so we don’t overbuild)
- If we need something to “look YC-level fast”, prioritize:
  - Phase 1 durability + HIL pause/resume semantics
  - Phase 3 GitHub integration with evidence-based validation (fastest impressive demo)
  - Phase 8 agent success metrics + approvals inbox polish
- **Active goal (post Phase 0A):** connect all 4 systems live (GitHub+Jira MCP, Gmail+Calendar native) with cloudflared webhooks — see `CONNECT.md` and `apps/api/`.

## Per-phase planning checklist (copy/paste)
- **Authority alignment**: which headings in `AUTHORITY.md` does this phase implement?
- **Contracts**: what schemas/interfaces are being added or changed?
- **Reliability**: retries/timeouts/idempotency/rate limits involved?
- **Security/governance**: policy + HIL impact?
- **Validation**: what evidence is required and how will it be verified?
- **UI**: what new surfaces are required (if Phase 8)?


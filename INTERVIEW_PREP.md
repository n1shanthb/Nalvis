# AgentSuite — Interview Prep

> AI / Agentic systems engineer role. Project: **AgentSuite** — single-tenant, multi-product agentic automation platform. Study guide, not a script.

---

## 1. 30-second pitch

> "AgentSuite is an agentic automation platform for a company running many products. You upload a company knowledge graph, it splits into product workspaces, and agents execute real work across GitHub, Jira, Gmail, Calendar. The differentiator: every action is **durable** (Temporal), **governed** (policy + human-in-the-loop), and **independently verified** — an agent can't just claim success; a separate Validation Agent re-queries the external system and returns PASS / FAIL / NO_EVIDENCE from machine-checkable evidence."

Land three words: **durable, governed, verifiable**.

---

## 2. Problem

- Companies run many products (payment gateway + customer portal), each with own repos, Jira boards, comms lists, calendars.
- Manual ops is repetitive: triage issues, PR reviews, customer replies, scheduling.
- Naive "LLM chatbot" approaches fail: not reliable (crash = lost work), not safe (wrong repo/recipient), not trustworthy (can't tell if work happened).
- AgentSuite = **executors with guardrails and proof**, not chatbots.

---

## 3. Architecture (whiteboard)

Three planes:
- **Control** — FastAPI + React: accept KG, start runs, serve status, webhook ingress.
- **Execution** — Temporal workers + OpenAI Agents SDK: durable workflows, agent jobs, connector I/O.
- **Data** — PostgreSQL (source of truth) + Redis (coordination).

Flow: Ops Console → FastAPI → Temporal (CompanyRunWorkflow → ProductRunWorkflow per workspace) → Activities → GitHub MCP / Jira MCP / Gmail REST / Calendar REST. Postgres holds runs/jobs/HIL; Redis rate-limits; workers are stateless.

---

## 4. Tech stack & why

| Concern | Choice | Why |
|---------|--------|-----|
| Durability | Temporal | State survives crashes; retries/timeouts/HIL signals first-class |
| API | FastAPI | Async, typed Pydantic, OpenAPI |
| Agent runtime | OpenAI Agents SDK | Tool-bound specialists, structured I/O, LLM optional |
| Source of truth | PostgreSQL 16 | Runs/jobs/approvals/policies/agents/audit, JSONB |
| Coordination | Redis 7 | Rate limits + locks, never source of truth |
| GitHub/Jira | MCP | Tool surfaces + REST helpers for evidence |
| Gmail/Calendar | Native Google APIs | OAuth refresh tokens, Pub/Sub inbound |
| Frontend | React 19 + Vite + TS | Ops console, not chat |
| Domain | portable_core (aip.*) | Testable engine separate from deployable apps |

**Hexagonal split**: `apps/` (api+worker) thin & deployable; `portable_core` holds domain logic, unit-testable without Temporal/Postgres. Domain doesn't depend on infrastructure.

---

## 5. The four probe words

**Async** — Handlers never do long work inline. Webhook → enqueue Temporal workflow → return <1s. Long calls live in activities. Bounded fan-out.

**Reliable** — Durable workflows with stable ID `company-run-{uuid}`; crash → replay from event log. Retries with backoff (reads aggressive, writes fewer to avoid dupes). Timeouts on every activity. Idempotency keys from `run_id+workspace_id+job_type+requested_action`. Failed writes → failed job + validation row, not swallowed.

**Scalable** — Workers stateless (Temporal owns state); add processes on `agentsuite-main` queue, no migration. API stateless, scale replicas. Bounded concurrency per run. Redis rate limits per integration family = backpressure.

**Why Temporal not Celery?** — Celery is a task queue, fire-and-forget; it doesn't own workflow state. Worker dies mid-run → Celery doesn't know how far you got; you rebuild with DB+glue. Temporal is a workflow engine: every step is an event in its DB, replays from last completed step. HIL is first-class (`workflow.wait_condition(signal)`) not a polling loop. Retries/timeouts/child-workflow fan-out for free. For a 5-step run that pauses for human approval for hours, Temporal is right; Celery forces reimplementing half of it.

---

## 6. Why Redis? Where?

**Role: coordination/backpressure, NOT source of truth.**

- Integration rate limiting: `check_rate_limit(key="integration:github", limit=20, window_sec=60)` before every external write — prevents 429s.
- Optional distributed locks for ops that must not run twice concurrently.
- Caching transient lookups safe to recompute.

**Critical point**: Postgres is source of truth (runs/jobs/approvals/policies/audit). Redis wiped → system still correct, only rate-limit counters reset. No run state, approval, or evidence lost. Conscious reliability trade — kept Redis out of the critical write path.

---

## 7. Where is the LLM called?

**Optional, for meaning only, never facts.** Locked "LLM vs deterministic split".

**Deterministic (no LLM) — facts & bounds:**
- KG ingest → inventory (what exists, who owns it, valid scope, which connectors configured now).
- Routing auditor → groundedness (repo in scope? agent executable? evidence contract exists?).
- Policy engine → allow/deny/HIL per action.
- Evidence contracts → required fields per job type.
- Validation → re-query + compare.

**LLM — meaning & capability:**
| Call site | Does |
|-----------|------|
| Agent synthesis (`kg/synthesizer.py`) | Propose specializations from inventory — missions, roles, tool allowlists; includes `unsupported` stubs for Slack/Notion/AWS named in KG |
| Director routing (`director/router.py` `_llm_route`) | Pick minimum specialist set for a signal; structured JSON jobs |
| Content drafting (`jobs/draft.py`) | Draft real PR review body / issue comment / email reply from PR/issue/mail facts before HIL (fixed `[agentsuite] PR review` placeholder) |
| Agents SDK runtime (`runtime/agents_sdk.py`) | Optional LLM path in executor; falls back to direct tool invoke |

**Key sentence**: "The LLM proposes; deterministic code verifies and bounds. LLM never decides scope, never decides allowed, never marks success — that's auditor + policy + validation. Anti-rules-engine: no giant `if complaint then...` tree; LLM handles semantics, code handles facts."

**No LLM key?** — Synthesis falls back to inventory-grounded catalog templates (system present + scope exists → specialization). Director uses webhook facts first (`pull_request` → `github.review_pr`). System runs end-to-end, just less smart on ambiguous objectives.

---

## 8. How is an agent created? What does it have?

**Creation (KG → agent):**
1. Ingest KG → deterministic inventory (repos, systems, scopes, attention hints).
2. Synthesize (LLM if configured, else catalog templates): per system present + scope, propose specialization from Authority catalog.
3. Audit (deterministic): tool ⊆ agent allowlist? ⊆ available systems? job type has evidence contract? Reject ungrounded.
4. Persist to Postgres with origin evidence (which KG node justified it).

**Agent record has:**
- `id`, `name` (e.g. `Nexus Pay GitHub PR Reviewer`)
- `role` (Authority specialization, e.g. `GitHubPRReviewerAgent`)
- `systemKey` (github/jira/gmail/calendar)
- `mission`
- `tool_scope` — **least privilege** (e.g. `["github.review_pr","github.read"]`)
- `job_types`
- `workspaceIds`
- `guardrails` — per-tool `allow`/`hil`/`deny`/`auto`, **derived per agent** not shared
- `status` — idle/active/unsupported
- `activation` — ready/blocked_missing_connector
- `origin_paths` — KG nodes justifying the agent
- `last_active_at`, run history, PASS/FAIL metrics by job type & workspace

**v1 executable catalog:**
- GitHubIssueManagerAgent, GitHubPRReviewerAgent, GitHubCICDAgent, JiraSyncAgent, GmailCommsAgent, CalendarSchedulerAgent
- ValidationAgent — **read-only**, no write tools, PASS/FAIL/NO_EVIDENCE
- DirectorAgent — **router not writer**, no external write tools

**Principles:**
- Agents are executors, not chatbots.
- Least privilege; unsupported agents get no tools.
- Discovery ≠ execution: KG mentions Slack/Notion/AWS → still create agent (stable identity) but `unsupported` with empty write tools, never fake-execute.
- Runtime activation: specialists idle until Director selects; sharing a tool family ≠ co-activation.
- Director ≠ executor: routing bugs caught by auditor; execution still goes Policy → HIL → Evidence → Validation.

---

## 9. A run end to end

Trigger: GitHub PR webhook (or Gmail inbound, or manual).
1. Webhook → FastAPI validates, records delivery, starts thin `GithubInboundWorkflow`, returns <1s.
2. Normalize/fetch signal activity → structured signal (repo, PR #, title, body).
3. Start `CompanyRunWorkflow` with signal + objectives.
4. Fan-out: per workspace → child `ProductRunWorkflow`.
5. Director route activity → propose jobs from catalog + signal facts.
6. Routing Auditor → accept/reject (scope, executable, allowlist, evidence contract).
7. Materialize accepted jobs in Postgres.
8. Per job: Policy evaluate → allow/deny/hil. If hil: draft content activity (LLM writes real review body from PR diff) → create HIL approval row → workflow waits on Temporal signal. Human approves/edits/denies → signal resumes.
9. Execute job activity → real connector write → returns evidence (issue URL, message_id, event_id).
10. Validate job activity → ValidationAgent re-queries independently → PASS/FAIL/NO_EVIDENCE.
11. Fan-in → aggregate, mark run status, persist report.

---

## 10. HIL — how it really works

Not a polling loop — Temporal-native:
- Job hits approval policy → workflow creates approval row → `workflow.wait_condition(lambda: self._approval_decision is not None)`.
- Console reads pending rows. User Approve/Edit/Deny → API `decide_approval` → sends Temporal signal `approval_decision`.
- Workflow wakes, applies edits, executes exactly once.

"HIL is a workflow pause, not an API poll. Durably waiting — survives worker restart, resumes when human clicks approve an hour later."

Policy toggles runtime-changeable (no redeploy): `gmail.send_external.hil_required`, `github.merge_pr.hil_required`. Apply immediately to new jobs.

---

## 11. Evidence & Validation

- Every job type has an evidence contract — required fields for "Succeeded":
  - `github.create_issue` → issue_url, repo, issue_number
  - `github.review_pr` → pr_url, review_id
  - `gmail.send_email` → message_id, thread_id
  - `calendar.create_event` → calendar_id, event_id
- Job cannot succeed without satisfying contract.
- ValidationAgent independently re-queries (read-only): PASS (matches), FAIL (contradiction/gone), NO_EVIDENCE (nothing verifiable).
- Failed executes also produce validation rows — Validation page reflects reality, not claims.

"This makes it trustworthy. LLM can hallucinate 'I created the issue'; validation catches it — no matching issue URL in GitHub."

---

## 12. Inbound signals

- Gmail: Pub/Sub → webhook → `GmailInboundWorkflow` → fetch → signal → skip system senders (mailer-daemon, bounces, self-sent) to avoid loops → start CompanyRun.
- GitHub: webhook → `GithubInboundWorkflow` → normalize → signal. `pull_request` → `github.review_pr`; `issues` → `github.comment_issue`.
- Director uses webhook facts BEFORE LLM; LLM only adds meaning for ambiguous objectives.
- Debounce: same delivery_id or Gmail thread → dedup, no duplicate runs.

---

## 13. Likely follow-ups

**Why not one LLM agent with tools (LangChain)?** — Reliability + trust. Single LLM is stateless across crashes, no durable HIL, can hallucinate success. I separate planning (LLM) from execution (deterministic activities + evidence contracts) and add independent validation. LLM is one component, not the system.

**Stop agent writing to wrong repo?** — Three layers: (1) workspace scope allowlist in Postgres; (2) Routing Auditor rejects out-of-scope before jobs exist; (3) execute-time smoke/app repo guard. Fail-closed by default.

**LLM hallucinates a tool call?** — Auditor checks tool ⊆ allowlist ⊆ available systems; else reject or agent `unsupported`. Even if a write happens, validation re-queries → NO_EVIDENCE if artifact missing.

**Gmail reply loops?** — Skip system senders (mailer-daemon, noreply, bounces), skip self-sent (From == connected mailbox), skip SENT-only labels. Reply targets original sender's `message_id`, never KG distribution lists.

**Director not a writer?** — Separation + safety. Routing bugs caught by auditor; execution still goes policy/HIL/evidence/validation. If Director had write tools, a routing bug = unauthorized write.

**How do agents scale?** — Workers stateless on one task queue; Temporal owns state; add workers without migration. Bounded fan-out per run; Redis rate limits per integration.

**Idempotency?** — Key from run_id+workspace_id+job_type+requested_action. Retried activity won't duplicate issue/review/email.

**How is an agent's tool surface decided?** — Least privilege from its job types; guardrails derived per agent from KG context + tool scope, not a shared hardcoded set. Operators can edit per tool (allow/hil/deny/auto).

**What if a connector is down?** — Agent marked `unsupported`/`blocked_missing_connector`; no fake execution. When wired later, same agent activates without re-deriving identity.

**Why separate ValidationAgent?** — Trust. The executor has incentive to claim success; an independent read-only agent re-checks. Separation of duties.

**Why PostgreSQL JSONB?** — Flexible payloads (requested_action, evidence, signal vary per job type) + relational indexes on run/job/workspace + audit. No schema migration per new job type.

**Observability?** — Run timeline (queued/started/director/job transitions/validation), integration call log (last successful call), webhook deliveries, Temporal UI (workflow histories, activity failures, retries).

---

## 14. Things to NOT say

- Don't call it a chatbot. "Agents are executors, not conversational."
- Don't say LLM does everything. "LLM proposes; code verifies."
- Don't say Redis stores runs. "Postgres is source of truth; Redis is rate limits."
- Don't say it's multi-tenant. "v1 is single-tenant."
- Don't hand-wave reliability. Give the concrete mechanisms: durable replay, idempotency keys, HIL signals, evidence contracts.

---

## 15. One-line closer

> "The goal isn't smarter agents — it's trustworthy autonomous execution. Durable so work survives, governed so it's safe, verified so you can prove it happened."

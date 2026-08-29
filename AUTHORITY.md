## Authority Document (Source of Truth)

This document is the **authoritative scope + architecture contract** for this project. If an implementation detail conflicts with this doc, the implementation is considered wrong unless this doc is updated via PR first.

## Product statement
Build a **single-tenant, multi-product agentic automation platform** that ingests a company knowledge-graph (KG) JSON, splits it into product workspaces (e.g., “GPay”, “GMaps”, “Gmail”), and executes real work across **GitHub, Jira, Gmail, and Calendar** via a mix of **MCP and native connectors**. All actions are governed by **policy + HIL controls**, and every action is independently verified by a **Validation Agent** with evidence-based pass/fail/no-evidence outcomes.

## End-result goals (resume-ready)
- **Distributed & scalable**: async execution, horizontally scalable workers, bounded concurrency, rate limits, backpressure.
- **Reliable by design**: durable workflows, retries/backoff, timeouts, idempotency keys, compensations where safe.
- **Governed autonomy**: dynamic per-action HIL toggles + allow/deny policies + least-privilege tool access.
- **Verifiable outcomes**: all “agent claims” must be supported by external evidence (URLs/IDs) or fail validation.
- **Operational excellence**: audit log, observability, run history, approvals inbox, and reproducible workflows.

## Anti-example-coding rule (locked — whole system)
Examples anywhere (this doc, `goallol.md`, `PHASES.md`, chat, comments, demos) are **pedagogical only**.

- **Do not** implement features “for that example” or only along the example’s path (specific product names, mail→GitHub pairings, one smoke repo story, one happy path).
- **Do** implement the **underlying concept**: general schemas, catalogs, policies, workflows, auditors, evidence contracts, and connector interfaces that remain correct when the scenario, channel, agent set, or company KG changes.
- Director routing, agent synthesis, HIL, validation, UI pages, and connector usage all inherit this rule.
- If a PR only works for the example case and would need a new `if`/branch for the next case, it is **wrong** under this Authority.

## Non-goals (explicitly out of scope for v1)
- Multi-tenant SaaS (v1 is **single tenant**).
- End-user “chatbot” experience (agents are not chatbots; they execute jobs).
- Building connectors beyond the four target systems (GitHub/Jira/Gmail/Calendar). (For v1, Gmail/Calendar may be native rather than MCP.)
- Replacing enterprise IAM; we implement scoped credentials and least privilege inside our app.

## Canonical architecture

### Core components
- **Control Plane API** (FastAPI)
  - Accept KG JSON uploads and “run” requests.
  - Maintains workspace configs, policies, approvals, and run metadata.
  - Starts Temporal workflows and serves run/approval/validation status to the frontend.

- **Temporal** (durable orchestration)
  - Owns workflow state, retries, timeouts, fan-out/fan-in, and long-running execution.
  - Workflows call Activities that run agents and call MCP tools.
  - Workflows pause for HIL approvals and resume via signals.

- **Execution Plane (Workers)**
  - Temporal workers execute Activities:
    - planning/decomposition
    - agent execution (OpenAI Agents SDK)
    - validation (read-only evidence checks)
  - Workers are horizontally scalable and stateless.

- **Data plane**
  - **Postgres**: source of truth for configs, policies, approvals, run indexes, and audit indexes.
  - **Redis**: caching, rate limiting, optional distributed locks (not the source of truth).

- **Integrations**
  - **MCP GitHub**, **MCP Jira**
  - **Native Gmail**, **Native Calendar** (v1 is allowed to be native; MCP is optional later)
  - All write operations must return evidence; all read operations must be reproducible.

### Technology decisions (locked)
- **Agent runtime**: OpenAI Agents SDK
- **Workflow engine**: Temporal (Python `temporalio`)
- **API**: FastAPI
- **Persistence**: Postgres + Redis
- **Connector strategy (v1)**: GitHub/Jira via MCP; Gmail/Calendar via native Google APIs with OAuth (webhooks optional per system).

## Domain model (authoritative nouns)

### Company
Single tenant. Owns:
- products (workspaces)
- integration credentials/config
- policy defaults

### Product Workspace (a “project” in this system)
Represents one product under the same company (e.g., GPay, GMaps).
Workspace defines:
- **Repo scope**: allowed GitHub org/repo list
- **Jira scope**: allowed Jira project keys/boards
- **Comms scope**: allowed Gmail labels/domains; stakeholder distribution lists
- **Calendar scope**: allowed calendar IDs; meeting templates
- **Policies**: action-level HIL and allow/deny rules

### Run
A top-level execution request:
- input: KG JSON + requested objectives (optional)
- output: a set of Jobs + a Validation Report

### Job (atomic unit of work)
One discrete intention, executed by one agent via specific tools.
Must include:
- `job_id` (UUID)
- `workspace_id`
- `job_type` (e.g., `github.create_issue`, `jira.transition`, `gmail.send`, `calendar.create_event`)
- `requested_action` (structured)
- `status` (queued/running/succeeded/failed/blocked_for_approval)
- `evidence` (structured; may be empty pending validation)

### Evidence
Machine-checkable identifiers/URLs proving work happened in the external system.
Evidence is required for “Succeeded” jobs.

### Validation outcome
- **PASS**: evidence exists and matches expected state.
- **FAIL**: evidence contradicts the claim or no longer exists.
- **NO_EVIDENCE**: the agent claimed success but provided nothing verifiable.
Note: internal systems may use additional verdict labels, but the public platform contract must surface the canonical trio above.

## LLM vs deterministic split (locked — anti-rules-engine)

Do **not** grow a giant semantic rules engine in the deterministic layer. Determinism establishes **facts and bounds**; the LLM establishes **meaning and capability**; an auditor checks **groundedness**.

### Deterministic layer establishes (facts / inventory / bounds)
- **WHAT EXISTS** — entities present in ingested context (products, repos, projects, calendars, mail groups, named systems like Slack/Notion/AWS, …) as structured inventory, not “what it means for automation.”
- **WHO OWNS IT** — company/tenant + which product workspace a scoped resource belongs to (from KG relationships / explicit ownership fields).
- **WHAT EVIDENCE SUPPORTS IT** — pointers back to KG paths / document ids that justify each inventory row.
- **WHAT SYSTEMS ARE ACTUALLY AVAILABLE** — which connectors are configured and executable *right now* (GitHub/Jira/Gmail/Calendar vs missing) vs merely mentioned.
- **WHAT SCOPE IS VALID** — allowlists and hard boundaries for writes (repo lists, jira keys, calendar ids, domains); policy/HIL toggles; schema validity.

Deterministic code may parse, normalize, validate schema, index relationships, and enforce allow/deny. It must **not** encode brittle semantic trees (“if complaint then …”, “if meeting then …”, department heuristics, etc.).

### LLM layer establishes (meaning / capability / specialization)
- **WHAT THIS WORK MEANS** — intent of a signal or objective in context of the company.
- **WHAT CAPABILITY IT REPRESENTS** — which automation capability classes apply.
- **WHAT AUTOMATION COULD HELP** — opportunities, including systems not yet connected.
- **WHAT AGENT SPECIALIZATION MAKES SENSE** — proposed agent missions, roles, tool allowlists drawn from the valid catalog, including `unsupported` stubs for unavailable systems.

### Deterministic auditor (groundedness gate)
After any LLM proposal (agent synthesis, Director routing, job plans):
- Is every referenced resource in the deterministic inventory and in-scope?
- Are proposed tools ⊆ agent allowlist and ⊆ **actually available** systems (else mark/create `unsupported`, never fake-execute)?
- Does each proposed write `job_type` have an evidence contract?
- Reject or rewrite proposals that are ungrounded; never “fix forward” by inventing facts.

This balance is mandatory for Director routing, agent creation, and run planning.

### Agent discovery vs agent execution (locked)
KG/context may mention **any** external system the company uses (Slack, Notion, AWS, GCP, Linear, Salesforce, etc.). The platform **must identify** those automation opportunities and **create Agent records** for them (mission, origin evidence, desired tool surface).

**v1 executable connectors (tools exist):** GitHub (MCP), Jira (MCP), Gmail (native), Calendar (native), plus read-only **ValidationAgent**.

**Unsupported-but-discovered agents:** If the KG implies automation on a system with **no connected tool surface yet**, still create the agent, set `status=unsupported` (or equivalent), `activation=blocked_missing_connector`, and **empty/deny write tools**. It appears in the Agents directory with a clear “not supported — connect {system} to activate” state. When that connector is later wired, the same agent can be activated without re-deriving identity from scratch.

Do **not** invent fake executors that pretend to act on Slack/Notion/AWS/etc. in v1. Discovery ≠ execution.

### Agent types (minimum executable set for v1)
Agents are **specialized executors** with minimal tool access. The following are the v1 **runnable** specializations (instantiated only when KG/scopes justify them):

- **GitHubIssueManagerAgent**
  - create/triage/label/assign issues within workspace repo scope

- **GitHubPRReviewerAgent**
  - add review comments, request changes, summarize checks (no merging unless policy allows)

- **GitHubCICDAgent**
  - propose or create CI workflow changes (write actions typically HIL-gated)

- **JiraSyncAgent**
  - create/link/transition tickets, sync status with GitHub artifacts

- **GmailCommsAgent**
  - draft/send emails, triage threads into tickets (external sending often HIL-gated)

- **CalendarSchedulerAgent**
  - schedule/reschedule meetings, attach agenda/templates (rescheduling exec meetings often HIL-gated)

- **ValidationAgent (read-only)**
  - re-queries MCP systems to verify evidence and emits PASS/FAIL/NO_EVIDENCE
  - must not have write tools

- **DirectorAgent (router / planner — not a writer)**
  - Chooses **which specialist agent(s)** should run for a given signal or objective.
  - Exists so we **do not** activate every agent that shares a connector (e.g. every agent with Gmail read).
  - **Generalized routing (locked):** see project-wide **Anti-example-coding rule**. Director classifies any signal/objective against the live agent catalog + scopes + allowlists; no scenario trees or fixed pairings.
  - Output is a structured **routing decision** (candidate jobs: `agent_id`, `job_type`, `requested_action`, confidence, rationale) — **no external write tools**.
  - A deterministic **Routing Auditor** must accept/reject the decision (workspace scope, agent status must be executable not `unsupported`, tool allowlist, evidence contract exists). Rejected routes do not become jobs.

### Runtime activation rule (locked)
Specialist agents are **idle until selected**. The Director (or an explicit human-started run objective) selects a **small set** of agents per signal. Sharing a tool family (e.g. `gmail.read`) does **not** imply co-activation.

### Guardrails (locked principles)
- **Least privilege tools**: each agent receives only tools needed for its job types (unsupported agents get none; Director has no write tools).
- **Workspace scoping**: tools must enforce workspace boundaries (no cross-product writes).
- **Policy gating**: tool calls that are “write” must consult Policy Engine; may require HIL.
- **Structured I/O**: all agent outputs are validated against schemas (Pydantic).
- **No mock execution**: unsupported agents must not emit synthetic success or fake evidence.
- **Director ≠ executor**: routing mistakes are caught by the Routing Auditor; execution still goes through Policy/HIL/Evidence/Validation.
- **Concept over example**: never code the illustration; code the abstraction (see Anti-example-coding rule).

## Temporal orchestration (authoritative workflows)

### CompanyRunWorkflow
Input: KG JSON + optional run objectives.
Steps:
- **Deterministic ingest:** parse/validate KG → inventory of what exists, ownership, supporting evidence pointers, valid scopes, and which connectors are actually available (see LLM vs deterministic split).
- **LLM synthesis:** propose agent specializations / automation opportunities from that inventory (meaning + capability — including unsupported systems as stubs).
- **Auditor:** groundedness check; persist accepted workspaces/agents only.
- For each workspace: start `ProductRunWorkflow` (fan-out with bounded concurrency).
- Aggregate job results (fan-in).
- Trigger validation for every job that claims success.
- Persist final run report and expose via API.

### ProductRunWorkflow(workspace_id)
Steps:
- **DirectorAgent (routing activity)**: given run objectives and/or inbound signals (e.g. email thread summary), propose which specialist agents/jobs to run — do **not** wake all agents that share a connector.
- **Routing Auditor (deterministic)**: accept/reject proposed jobs (scope, executable agent only, tool allowlist, evidence contract).
- Materialize accepted jobs in Postgres.
- Execute jobs in parallel where safe (bounded concurrency).
- For any gated action: pause and wait for approval signal.
- Record per-job audit events.

### ValidationWorkflow(run_id or job_id)
Steps:
- For each job: fetch evidence requirements by `job_type`.
- Re-query external systems via read-only connectors (MCP for GitHub/Jira; native read APIs for Gmail/Calendar).
- Emit PASS/FAIL/NO_EVIDENCE + attach evidence references.

## Human-in-the-loop (HIL) and policy engine

### Policy toggles (dynamic; runtime changeable)
Policies must be changeable without redeploy and apply immediately to new jobs.
Examples:
- `github.merge_pr.hil_required` (true/false)
- `github.merge_pr.auto_merge_enabled` (true/false; independent of HIL)
- `gmail.send_external.hil_required`
- `calendar.reschedule_exec.hil_required`

### Approval flow (contract)
- When a job hits an action requiring approval:
  - workflow transitions job to `blocked_for_approval`
  - API exposes an approval item in an “Approvals Inbox”
  - user approves/denies with optional edits
  - workflow resumes via Temporal signal with immutable approval record

## Evidence contracts (authoritative minimum)
Each job type defines evidence fields required for “Succeeded”:

- `github.create_issue` → `issue_url`, `repo`, `issue_number`
- `github.review_pr` → `pr_url`, `review_comment_urls[]` or `review_id`
- `github.create_or_update_workflow` → `repo`, `commit_sha`, `file_path`, `workflow_url`
- `jira.create_ticket` → `issue_key`, `browse_url`
- `jira.transition_ticket` → `issue_key`, `transition_id` (or changelog marker)
- `gmail.send_email` → `message_id`, `thread_id`
- `calendar.create_event` → `calendar_id`, `event_id`
- `calendar.update_event` → `calendar_id`, `event_id`

If evidence is missing or unverifiable, validation must not PASS.

## Observability & audit (must-have)
- **Audit log**: append-only events for every job state transition and every external tool call (request metadata, response metadata, timestamps, errors).
- **Tracing**: distributed traces across API → Temporal workflow → Activity → MCP call.
- **Run timeline**: reconstructible UI timeline from audit events.

## Frontend (authoritative UX scope)
We ship a simple but professional UI (internal console) with:
- **KG Upload / Workspace Preview**
  - upload KG JSON
  - preview derived product workspaces and their scopes (repos/jira keys/calendars)
- **Runs**
  - create run, list runs, filter by workspace/status
  - run detail: DAG/timeline view of jobs, retries, approvals, validation outcomes
- **Approvals Inbox (HIL)**
  - pending approvals, view job intent + diff-like preview, approve/deny/edit
- **Policies**
  - per-workspace toggles for HIL and action permissions
  - separate toggle for auto-merge vs HIL
- **Integrations Health**
  - credentials status, last successful call per integration, rate limit indicators
- **Validation Reports**
  - pass/fail/no-evidence breakdown, evidence links, validator reasoning + raw checks
- **Agents**
  - directory of created agents with: name, role, tool scope summary, workspace(s), creation time, and current status
  - per-agent **profile**: mission, origin evidence (why the agent was synthesized from ingested KG/context), full specs (model/runtime/tool contracts), and **agent-specific guardrails**
  - guardrails are **derived per agent** from ingested context + tool scope (not a shared hardcoded set); operators can add/edit rules per tool with allow / HIL / deny / auto-run
  - per-agent run history: runs participated in, jobs executed, last active time, and most common job types
  - success metrics computed from validation outcomes:
    - overall PASS/FAIL/NO_EVIDENCE rates
    - breakdown by job type (e.g., `github.review_pr`, `jira.transition_ticket`)
    - breakdown by workspace (product)
  - drilldowns from an agent → a specific job → evidence links → validator checks

Frontend is not a chat UI. It is an operations console for runs/jobs/approvals/validation.

**Anti-fake-data rule:** The ops console must not ship synthetic/seeded operational records (fake runs, agents, approvals, integrations health, or validation outcomes). Empty lists and explicit empty/error states are required when the control plane has no data. Parse-preview of operator-pasted input is allowed; inventing tenant history is not.

## KG JSON (placeholder until sample provided)
We will define and lock the KG schema after a sample is provided. Until then:
- KG must be able to represent: products, repos, jira projects, calendars, email groups, stakeholders, relationships, and named external systems.
- The **deterministic** layer extracts inventory + ownership + evidence pointers + valid scopes + connector availability from KG relationships.
- The **LLM** layer interprets what automation/agents that inventory implies; the **auditor** enforces groundedness. Do not replace LLM meaning with a hand-coded semantic discovery engine.

## Change control (anti-drift rule)
- Any change to scope, workflow semantics, evidence requirements, or UI pages must update this doc in the same PR.
- “It works in code” is not acceptable if it violates this document.


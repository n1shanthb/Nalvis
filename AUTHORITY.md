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

## Multi-agent system design

### Agent types (minimum set for v1)
Agents are **specialized executors** with minimal tool access.

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

### Guardrails (locked principles)
- **Least privilege tools**: each agent receives only tools needed for its job types.
- **Workspace scoping**: tools must enforce workspace boundaries (no cross-product writes).
- **Policy gating**: tool calls that are “write” must consult Policy Engine; may require HIL.
- **Structured I/O**: all agent outputs are validated against schemas (Pydantic).

## Temporal orchestration (authoritative workflows)

### CompanyRunWorkflow
Input: KG JSON + optional run objectives.
Steps:
- Parse KG → derive `ProductWorkspace[]` candidates and their scopes.
- For each workspace: start `ProductRunWorkflow` (fan-out with bounded concurrency).
- Aggregate job results (fan-in).
- Trigger validation for every job that claims success.
- Persist final run report and expose via API.

### ProductRunWorkflow(workspace_id)
Steps:
- Create an execution plan for the workspace.
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

## KG JSON (placeholder until sample provided)
We will define and lock the KG schema after a sample is provided. Until then:
- KG must be able to represent: products, repos, jira projects, calendars, email groups, stakeholders, and relationships.
- The system must deterministically derive workspace scopes from KG relationships.

## Change control (anti-drift rule)
- Any change to scope, workflow semantics, evidence requirements, or UI pages must update this doc in the same PR.
- “It works in code” is not acceptable if it violates this document.


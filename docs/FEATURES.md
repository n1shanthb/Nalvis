# Features & Capabilities

AgentSuite is a **governed automation platform** for companies with multiple products. It turns organizational context (knowledge graphs, scopes, policies) into **executable, verifiable work** across developer and comms systems.

---

## Product model

### Company → workspaces → agents

- **Company** — single tenant; owns integration credentials and policy defaults.
- **Product workspace** — one product line (e.g. Resume Analytics, Ops Console) with scoped repos, Jira keys, email groups, calendars.
- **Agents** — specialized executors, not chatbots. Idle until the Director selects them for a signal or run objective.

Context enters via **Context Studio**: upload or paste KG JSON (graph or structured). The platform:

1. **Deterministically** parses inventory — repos, systems, stakeholders, scopes.
2. **Synthesizes** agent specializations (LLM when configured) from catalog templates.
3. **Audits** proposals for groundedness — no writes to out-of-scope resources.
4. **Persists** workspaces, agents, guardrails, and default policies.

Systems mentioned in the KG but without connectors (Slack, Notion, AWS, …) appear as **unsupported agents** — visible in the directory, blocked from execution until wired.

---

## Runnable agent specializations (v1)

| Agent | System | Typical jobs |
|-------|--------|--------------|
| **GitHub Issue Manager** | GitHub | Create issues in repo scope |
| **GitHub PR Reviewer** | GitHub | Review comments on pull requests |
| **GitHub CI/CD** | GitHub | Create or update workflow files (HIL-gated) |
| **Jira Sync** | Jira | Create / transition tickets |
| **Gmail Comms** | Gmail | Send mail, reply to inbound threads (HIL-gated) |
| **Calendar Scheduler** | Calendar | Create / update events |
| **Validation** | Read-only | Re-fetch evidence; emit PASS / FAIL / NO_EVIDENCE |
| **Director** | Router only | Classify signals → structured job plan; no write tools |

Agents receive **least-privilege tool scopes**. The Director activates a small set per run — sharing a connector family does not mean all agents on that connector run.

---

## Job types & evidence

Every executable job type has an **evidence contract** — required fields before a job can succeed:

| Job type | Evidence (examples) |
|----------|---------------------|
| `github.create_issue` | `issue_url`, `repo`, `issue_number` |
| `github.review_pr` | `pr_url`, `review_id` or review URLs |
| `github.comment_issue` | `issue_url`, `comment_id`, `repo` |
| `github.create_or_update_workflow` | `repo`, `commit_sha`, `file_path`, `workflow_url` |
| `jira.create_ticket` | `issue_key`, `browse_url` |
| `gmail.send_email` | `message_id`, `thread_id` |
| `calendar.create_event` | `calendar_id`, `event_id` |

Claims without verifiable IDs fail validation — the platform does not trust agent prose alone.

---

## Governance

### Policy engine

Per-workspace rules for each action: **allow**, **deny**, or **require HIL**. Defaults gate sensitive writes (PR reviews, external email, workflow commits, calendar reschedule).

### Human-in-the-loop (HIL)

When policy requires approval:

1. Job blocks in Temporal workflow.
2. Approval appears in the project **Approvals inbox** with before/after action preview.
3. Operator **approves**, **denies**, or **edits & approves**.
4. Workflow resumes via Temporal signal; execute proceeds or fails accordingly.

Audit trail: run timeline, approval records, integration call timestamps.

### Routing auditor

Before any job materializes, a deterministic auditor checks:

- Agent exists and is executable (not `unsupported`).
- Job type is in agent tool allowlist.
- Target repo / Jira project / calendar is in workspace scope (with smoke/app allowlist for credentialed repos).
- Evidence contract exists for the job type.

Rejected routes never become jobs.

---

## Inbound automation

Webhook ingress is thin at the API boundary; durable processing runs in Temporal.

| Source | Events (examples) | Routed jobs |
|--------|-------------------|-------------|
| **GitHub** | PR opened/sync, issue opened | `github.review_pr`, `github.comment_issue` |
| **Gmail** | Pub/Sub watch, simulate API | Reply to external sender via `message_id` |
| **Jira** | Issue / comment events | Director + LLM or structured plan |

Gmail inbound **replies to the original sender**, not KG distribution lists. System mail (bounces, mailer-daemon, self-sent) is filtered.

**Integrations** page: connector health, last successful call, inbound tunnel start/stop, copyable webhook URLs.

---

## Ops console pages

| Page | Purpose |
|------|---------|
| **Ops console** | Company graph, agent strip, Temporal timeline, health stats |
| **Context Studio** | KG ingest, parse preview, clear state |
| **All projects** | Workspace list |
| **Overview** | Project scope summary |
| **Runs** | Company runs, job DAG, timeline |
| **Approvals** | HIL inbox (project-scoped) |
| **Policies** | Per-action allow / HIL / deny |
| **Validation** | PASS / FAIL / NO_EVIDENCE with checks and evidence refs |
| **Agents** | Catalog, specs, guardrails, metrics |
| **Integrations** | Live connector status + tunnel |

UI rule: **no synthetic operational data**. Empty states are intentional until real runs exist.

---

## Director & LLM

The Director classifies objectives and inbound signals against the **live agent catalog** — not hardcoded scenario trees.

Routing priority:

1. Explicit run plan (API / human)
2. Structured jobs on signal (`requested_jobs`)
3. GitHub / Gmail webhook fact families → catalog job types
4. LLM classification (OpenAI-compatible: OpenAI or OpenRouter)
5. Empty decision with note (no invented paths)

Deterministic layer owns **facts and bounds**; LLM owns **meaning and capability**; auditor owns **groundedness**.

---

## Cross-system runs

A single company run can fan out to multiple workspaces. Ship smoke and manual plans can combine GitHub + Gmail + Calendar + Jira jobs in one run, with validation per succeeded job.

Idempotency keys deduplicate retries on the same run + workspace + job type + action payload.

---

## What v1 explicitly does not do

- Multi-tenant SaaS isolation
- End-user chat interface
- Executable connectors beyond GitHub, Jira, Gmail, Calendar
- Fake success or mock evidence for unsupported systems

See [AUTHORITY.md](../AUTHORITY.md) for the full contract.

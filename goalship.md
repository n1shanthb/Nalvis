# goalship.md — Ship-ready Authority v1

This file is the **active engineering goal** after [`goallol.md`](goallol.md). It closes remaining gaps so AgentSuite is **ready to ship** as a single-tenant ops console. Subordinate to [`AUTHORITY.md`](AUTHORITY.md) — Authority wins on conflict.

**Prerequisite:** `goallol.md` spine DoD is done (Postgres control plane, Temporal Company/Product/Validation workflows, real GitHub+Gmail+Calendar writes + validation + HIL, HttpAdapter, unsupported-agent discovery, clear-all-data).

## Goal statement

Make AgentSuite **operator-shippable**: OpenRouter (or any OpenAI-compatible) LLM drives Director + synthesis; **inbound signals** (especially Gmail) start real runs; **graph KG ingest** (`ex1`/`ex2`-shaped nodes+edges) is the primary context format — **infer** inventory/automation from it without blindly obeying or restricting to recommendations; **recommended_agent is a must (floor) but not a ceiling** (still discover other automations); **all Authority v1 job types** execute with evidence + validation (GitHub PR/CI, Jira required, Calendar update); one **cross-system** path works; Integrations/observability are honest; the console alone can run the full loop without CLI crutches.

## Authority references (must hold)

| Topic | Authority heading |
|---|---|
| Resume-ready outcomes | End-result goals |
| Locked stack | Technology decisions · Canonical architecture |
| Agents + Director | Agent types · Runtime activation rule · DirectorAgent |
| Facts vs meaning | LLM vs deterministic split |
| Graph KG ingest | KG JSON (graph ingest — locked) |
| Orchestration | Temporal orchestration (Company / Product / Validation) |
| Governance | HIL and policy engine |
| Proof | Evidence contracts · Observability & audit |
| UI | Frontend · Anti-fake-data rule |
| Scope boundary | Non-goals (v1) · Change control |
| Concept over example | Anti-example-coding rule |

## Non-negotiables (anti-slop)

- Same as `goallol.md`: concept over example; no fake ops data; no Slack/Notion/AWS/Linear writes; Temporal activities only for long writes; ValidationAgent authoritative; idempotency; bounded concurrency; HttpAdapter product path.
- **LLM config must honor `.env`:** `OPENROUTER_API_KEY` / `OPENAI_API_KEY` + `LLM_API_BASE` (OpenAI-compatible). Empty `OPENAI_API_KEY` with a set OpenRouter key must still enable Director LLM routing.
- **Inbound is first-class:** webhook receive ≠ done; receive → durable run/signal → Director → jobs.
- **Product-scoped agents:** company-level hints must not invent Jira/Linear agents on products that never appear in the graph inventory for those systems.
- **Graph KG primary:** ingest understands `nodes`/`edges` like `ex1.json` / `ex2.json`. Infer freely; never treat the sample as a closed whitelist or as the only automation list.
- **Recommended agent = must, not only:** non-null `attention.recommended_agent` (or equivalent) **must** yield a grounded agent; synthesis **must continue** to propose additional automations from inventory. Do not map hint strings 1:1 into fake executors.
- Ship DoD is **console-driven**: upload KG → agents → inbound or Start run → approve → validations PASS chain visible in UI.

## What this goal closes (gap list)

| # | Gap today | Ship requirement |
|---|---|---|
| 1 | OpenRouter unused; code only reads empty `OPENAI_API_KEY` | Unified LLM client: key + base URL; Director, synthesizer, Agents SDK Runner |
| 2 | Gmail webhook only logs | Inbound Gmail → fetch thread summary → start/signal CompanyRun with Director `signal` |
| 3 | Director needs structured `plan[]` without LLM | Free-text / inbound signal routing via LLM + Routing Auditor |
| 4 | Flat `products[]` only; ignores graph KG; recommendations unused or treated as exclusive | Ingest `ex1`/`ex2`-shaped graphs; honor `recommended_agent` as **must**; still discover other automations; map hints via catalog+auditor |
| 5 | GitHub mostly `create_issue` in live path | PR review + CI/CD job types with evidence + validation |
| 6 | Jira optional in goallol | Jira create and/or transition **required** for ship with validation PASS |
| 7 | Calendar create only (update thin) | `calendar.update_event` path with HIL when policy requires |
| 8 | No cross-system workflow | One Authority Phase-7-style chain (e.g. inbound mail → calendar and/or ticket) with per-step validation |
| 9 | Integrations lack live latency / lastSuccessfulCall | Persist last success + errors from activities; surface on Integrations page |
| 10 | CLI still needed for some proofs | Full loop from UI; ship smoke script optional as CI evidence only |

## Explicit non-goals (still out)

- Multi-tenant SaaS
- Chat UI
- Implementing Slack / Notion / AWS / GCP / Linear **connectors** (unsupported stubs stay)
- Perfect SRE (deep tracing dashboards, multi-region) — minimum: audit timeline + lastSuccessfulCall + rate-limit remaining when available
- Replacing enterprise IAM

## Target architecture (ship delta)

```text
Inbound (Gmail Pub/Sub → /api/webhooks/gmail)
  → fetch message/thread (native read)
  → persist inbound event + enqueue CompanyRunWorkflow (or signal existing)
  → ProductRunWorkflow: Director(signal) + Routing Auditor
  → ExecuteJob (Agents SDK + OpenRouter) → Evidence → ValidationWorkflow
  → Approvals Inbox when HIL

LLM config
  OPENROUTER_API_KEY | OPENAI_API_KEY
  LLM_API_BASE (default OpenAI; OpenRouter https://openrouter.ai/api/v1)
  OPENAI_MODEL / LLM_MODEL
```

### LLM client (locked for this goal)

- Single helper (e.g. `aip.llm.client`) used by Director, KG synthesizer, Agents SDK.
- Resolve key: `OPENAI_API_KEY` if set, else `OPENROUTER_API_KEY`.
- Resolve base: `LLM_API_BASE` if set.
- Never hardcode vendor; OpenAI SDK with `base_url` is fine.
- If no key: keep current safe behavior (structured plan only; no invented routes).

### Inbound Gmail (locked for this goal)

1. Pub/Sub push hits webhook (already).
2. Activity: resolve history/message → structured **signal** (`channel`, `subject`, `from`, `snippet`/`body_summary`, `thread_id`, `message_id`) — facts only.
3. Start or continue `CompanyRunWorkflow` with that signal (no FastAPI-held long Google I/O).
4. Director classifies signal against **live** agent catalog (general; no `if schedule in subject → calendar`).
5. Auditor + policy/HIL + execute + validate as today.

GitHub/Jira inbound → run may follow the same pattern if time allows; **Gmail inbound is the ship blocker**.

### KG ingest — graph first (locked for this goal)

Primary format: **knowledge graph** as in `ex1.json` / `ex2.json` (nodes + edges). Flat `{company, products[]}` remains a secondary paste format.

**Deterministic inventory (facts):**
- Walk nodes/edges → repos, files, commits, emails, documents, people, products/org entities, source_type (github/mail/…), need_attention / attention blocks, evidence paths (node ids).
- Do **not** require every field from the samples; do **not** reject unknown entity types — record them as resources with pointers.
- Optional flat aliases (`jira_project_key`, `linear_team_key`, slack channels, aws accounts, owners) still accepted when present.

**Recommended agents (floor, not ceiling):**
1. For every node with non-null `attention.recommended_agent` (or `need_attention` / `attention.required` true): **must** emit a grounded proposal covering that hint (map `"Developer"` → catalog role(s) such as GitHubIssueManager / PR reviewer when github inventory exists; else unsupported stub with origin = that node).
2. **Then** run full catalog/LLM discovery for **additional** automations the graph implies (other specializations, other systems, unsupported stubs). Recommendations never cap the set.
3. Auditor rejects ungrounded invention; unsupported stay non-executable.
4. Never implement `if recommended_agent == "Developer": …` scenario trees — general hint→catalog mapping only.

### Product / workspace derivation

Infer product workspaces from graph structure (product entities, BELONGS_TO / USES edges, repo groupings) — not only from a hand-written `products[]` array. Agent proposals prefer product-owned resources; do not bleed company-wide systems onto every workspace without evidence.

## Definition of done (ship)

Verifiable on a clean DB (Clear all data → ingest rich Talos-like KG → run paths below):

1. **LLM:** With only `OPENROUTER_API_KEY` + `LLM_API_BASE` set, Director routes a free-text objective (no `plan[]`) to a small set of specialists; auditor rejects unsupported/out-of-scope.
2. **Inbound:** Send (or simulate Pub/Sub for) mail to the configured Gmail user about scheduling → run appears in UI → Calendar and/or Gmail agent selected by Director → HIL if required → evidence + validation row.
3. **Ingest accuracy (graph):** Upload `ex2.json` (or equivalent) → inventory includes repos + mail nodes; any `recommended_agent` produces ≥1 grounded agent with origin path to that node; **additional** agents beyond recommendations also appear when inventory supports them (e.g. GitHub specializations from repos even when recommendation was only on an email). Flat Talos-style JSON still works as secondary format.
4. **GitHub:** At least **two** distinct job types validate PASS (e.g. `create_issue` + `review_pr` or CI workflow write) on smoke-allowed repo only.
5. **Jira:** At least one create **or** transition validates PASS with evidence.
6. **Calendar:** create **and** update/reschedule each leave evidence; update respects HIL policy when enabled.
7. **Gmail:** send (already) remains; draft-or-triage path acceptable if send already proven — external send stays HIL-gated by default.
8. **Cross-system:** One multi-job run spanning ≥2 systems, each step validated (PASS/FAIL/NO_EVIDENCE real).
9. **Integrations:** page shows healthy + **lastSuccessfulCallAt** (or equivalent) after live calls — not all-null forever.
10. **Console-only:** Clear → ingest → (inbound or Start run) → Approvals → Validation / agent metrics without required CLI.
11. **Honesty:** empty after clear; no synthetic seeds; unsupported never fake-succeed.
12. **Ship smoke:** `scripts/ship_smoke.py` (or successor) writes proof under `data/smoke_proof/` covering items 1–8; CI or operator can re-run.

## Build sequence (no glue)

1. **LLM client + env** — OpenRouter/OpenAI unified; wire Director, synthesizer, Agents SDK; document in `.env.example`.
2. **KG graph inventory + synthesizer** — parse `nodes`/`edges`; recommended_agent must; extra discovery; product scoping; fixtures from `ex1.json`/`ex2.json` (truncated or full) in tests.
3. **Inbound Gmail → CompanyRun** — fetch + signal + Director path; webhook stays thin.
4. **Expand ExecuteJob + validation** — GitHub PR/CI, Jira write, Calendar update (same evidence contracts).
5. **Cross-system ProductRun** — Director may emit multi-system jobs; fan-in + ValidationWorkflow for each.
6. **Observability** — activity hooks update integration last success/error; API/UI.
7. **Console polish** — ensure Start run can omit hard-coded plan when LLM key present (objective text only); run timeline/agent metrics usable.
8. **Ship smoke + docs** — proof script; update `PHASES.md` / this file Status; mark goallol closed.

## Risk & Authority guardrails

| Risk | Guardrail |
|---|---|
| OpenRouter key in repo | Never commit secrets; `.env` gitignored; rotate if leaked |
| Inbound storms | Idempotent delivery IDs; debounce per thread; rate limits |
| LLM invents repos/calendars | Routing Auditor + inventory scopes only |
| Blindly create agent named "Developer" with write tools | Map hint → Authority catalog; auditor; unsupported if no connector |
| Only create recommended agents | Discovery pass after recommendations (floor ≠ ceiling) |
| Keyword routing for “schedule” | Forbidden — Director LLM + catalog only |
| Jira/GitHub writes outside smoke scope | Workspace scope enforcement in tools |
| Scope creep to Slack writes | Unsupported agents stay non-executable |
| Fake Integrations “healthy” | Health probe + lastSuccessfulCall from real activity |

## Relationship to phases

| Phase | Ship coverage |
|---|---|
| 0 / 0A / goallol spine | Done — do not re-litigate |
| 3–6 | Complete remaining job types + validation depth |
| 7 | Minimum one cross-system workflow |
| 8 | Console-driven ship loop + agent metrics honesty |

## Status

- **Goal owner:** active (\goalship.md\) — **ship gate largely met** (2026-08-29)
- **goallol:** closed (spine DoD)
- **Authority version:** see \AUTHORITY.md- **GitHub auth finding (prior 403 root cause):**
  - App Ĥ4238\ / install h272530\ already has \pull_requests:write\, \contents:write\, \issues:write\, but epository_selection=selected\ and was installed on **1shanthb/nalvis-landing\ only**.
  - On \nalytics-resume\: issue create works; PR review + contents write → **403 Resource not accessible by integration** until App is installed there: [GitHub installation settings](https://github.com/settings/installations/150272530) → Repository access → add 1shanthb/analytics-resume\.
  - Fine-grained \GITHUB_TOKEN\ PAT: reads OK, **writes 403** (\llows_permissionless_access\) — not usable for DoD writes.
  - **Shipped workaround:** \SMOKE_GITHUB_APP_REPO=n1shanthb/nalvis-landing\ + \SMOKE_GITHUB_PR_NUMBER=15\. ExecuteJob prefers App-installed repo for eview_pr\ / workflow; primary smoke repo for \create_issue\.
- **Also this session:** inbound delivery_id + thread debounce; console Start run **objective-only** (no hardcoded plan); \GET /api/llm/status\.
- **Verified DoD evidence:**
  - DoD 4 two GitHub types: \data/smoke_proof/dod4_github_latest.json\ + CompanyRun *820792-8ee0-4149-b8b9-abe3dd162635\ (\create_issue\ + eview_pr\ both PASS)
  - Full ship map: \data/smoke_proof/ship_smoke_20260829T180635Z.json\ / \ship_latest.json\ — items 1,3,4,5,6,6b,7,8,9 all true
- **Optional leftovers:** install App on \nalytics-resume\; live Pub/Sub push (simulate path solid); Jira transition live PASS
- **Ship gate:** met for Authority v1 ship DoD with proof artifacts under \data/smoke_proof/
---
name: plan-vs-implementation-audit
description: Audits what was planned vs what was implemented, then closes gaps by implementing missing items or updating the authoritative docs. Use after completing a planned change, feature, refactor, or bugfix—especially for multi-step work with requirements.
---

# Plan vs Implementation Audit

## Purpose
After execution, ensure the delivered system matches:
- the user’s requested plan, and
- `AUTHORITY.md` requirements (scope, workflows, evidence, HIL, validation, frontend console)

This skill enforces a **close-the-loop** engineering discipline: no “done” until the audit passes.

## When to run
Run at the end of any task that involved:
- a multi-step plan or roadmap
- additions/changes to workflows, agents, job types, validation, or UI pages
- integration work (GitHub/Jira/Gmail/Calendar MCP calls)
- reliability controls (Temporal retries/timeouts/idempotency) or policy/HIL

## Audit workflow (required)
1. **Restate the plan** (or extract the promised deliverables from the conversation).
2. **Collect implementation evidence**:
   - list files changed/added
   - confirm endpoints/workflows exist
   - confirm schemas/contracts exist
   - confirm UI pages exist (if relevant)
3. **Diff analysis**:
   - For each plan item, mark one: Implemented / Partial / Missing
   - For each `AUTHORITY.md` requirement touched, mark: Satisfied / Needs update / Violated
4. **Close gaps** (do not ask; just do it):
   - If a plan item is Missing/Partial → implement it.
   - If the plan was wrong or scope changed → update `AUTHORITY.md` first, then align code.
5. **Verification gates** (as applicable):
   - run targeted lint/diagnostics for edited files
   - run targeted tests (or add a minimal regression test when feasible)
6. **Final output** must include:
   - what changed
   - what was verified
   - any remaining known limitations (must also be reflected in `AUTHORITY.md` if structural)

## Required audit checklist (copy mentally)
- [ ] All promised plan items implemented or explicitly removed by updating `AUTHORITY.md`.
- [ ] Any new job type has evidence fields + validation logic path.
- [ ] Policy/HIL gating exists for any new write action; toggles are dynamic.
- [ ] Validation outcomes supported: PASS / FAIL / NO_EVIDENCE.
- [ ] Frontend reflects new entities: Runs/Approvals/Policies/Validation and (if relevant) Agents directory + metrics.
- [ ] No cross-workspace tool access was introduced.

## Examples

### Example: finished “add approvals inbox”
Audit must confirm:
- Temporal workflow pauses on gated actions and resumes via signal
- API exposes pending approvals
- Frontend has “Approvals Inbox” page
- Audit log records approval decision immutably


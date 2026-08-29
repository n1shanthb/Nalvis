---
name: root-cause-debugging
description: Enforces root-cause debugging over superficial patching. Use when the user pastes an error/stack trace or says “fix this bug,” “debug,” “it’s broken,” or “runtime error,” especially in frontend/backend pages where quick patches are tempting.
---

# Root-Cause Debugging (No Band-Aid Patches)

## Core rule (non-negotiable)
When asked to fix an error, **do not apply a local/symptom patch** (e.g., adding null checks, try/catch, disabling a rule, hiding a failing component) unless you can prove it addresses the **root cause**.

> If a user says “fix error on page X”, do not only patch page X. Trace the failure to the underlying cause (data contract mismatch, state machine bug, race, permissions/policy, integration response shape, workflow semantics) and fix it at the correct layer.

## What “patching the area” means (avoid)
Avoid “fixes” like:
- swallowing exceptions (`try/except: pass`)
- disabling lint/type checks to ship
- adding conditional rendering to hide the crash without fixing data source
- adding ad-hoc mapping logic in the UI to compensate for broken API schema
- hardcoding values to bypass orchestration/policy/validation

These are acceptable only when explicitly documented as an intentional mitigation and accompanied by a follow-up task—and in this repo, such mitigations must be reflected in `AUTHORITY.md` if they change system semantics.

## Debug workflow (required)
1. **Capture the failure**
   - Ask for or extract: error text, stack trace, reproduction steps, expected vs actual behavior.
   - Identify: component/service, request path, workflow/job, agent/tool involved.

2. **Reproduce deterministically (preferred)**
   - Run the smallest reproduction.
   - If reproduction requires integration calls, use mocks/stubs where feasible.

3. **Trace causality across layers**
   - UI → API response contract → DB state → Temporal workflow/activity → agent output schema → MCP tool response
   - Identify the **first wrong fact** (the earliest point where reality diverges from expectation).

4. **Fix at the source of truth**
   - Schema/contract mismatches: fix the producer (API/agent schema), not the consumer UI.
   - Workflow state bugs: fix workflow/activity semantics and idempotency, not UI workarounds.
   - Policy/HIL issues: fix policy evaluation and evidence gating, not agent prompts.
   - Integration parsing: fix tool wrapper + validation, not downstream nodes.

5. **Add verification**
   - Add/extend a regression test when feasible.
   - At minimum: add a deterministic check (schema validation, unit test, or workflow test) proving the root cause is fixed.
   - Run targeted lints/diagnostics for edited files.

6. **Post-fix audit**
   - Confirm the fix does not violate `AUTHORITY.md`:
     - evidence contracts preserved
     - policy/HIL gating not bypassed
     - validation semantics unchanged (PASS/FAIL/NO_EVIDENCE)
     - frontend remains an ops console (not chat UI)

## Output expectations (what you report back)
- **Root cause** (one sentence)
- **Fix** (what changed at the correct layer)
- **Why it’s correct** (what invariant is restored)
- **How it was verified** (tests/lints/repro)
- **Any remaining limitations** (must be explicit; update `AUTHORITY.md` if structural)

## Examples

### Example: UI crash “cannot read property jobs of undefined”
Bad: add optional chaining in UI only.
Good: trace to API returning `jobs=null` due to serialization/schema mismatch; fix API response model; add contract test; then keep UI rendering strict.

### Example: “PR reviewer says reviewed but validation fails”
Bad: mark validation PASS when evidence missing.
Good: fix PR reviewer tool wrapper to return `review_id` / comment URLs; ensure validator checks the review exists via GitHub MCP; add an integration-test stub to assert evidence present.


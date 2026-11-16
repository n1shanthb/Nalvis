---
name: authority-anchored-planning
description: Enforces that every plan, scope decision, and architecture change is anchored to AUTHORITY.md. Use when the user asks for a plan, scope, architecture, roadmap, MVP definition, or changes that may drift from the Authority Document.
---

# Authority-Anchored Planning

## Non-negotiables
- `AUTHORITY.md` is the **single source of truth**. Do not introduce requirements, components, workflows, or UI pages that contradict it.
- If the user requests something that is not covered or conflicts, **update `AUTHORITY.md` first** (or in the same change-set) before implementing.
- Plans must be **traceable** to `AUTHORITY.md` sections (explicit references by heading name).

## Quick start (when user asks for a plan)
1. **Read `AUTHORITY.md`** and extract the relevant constraints:
   - locked tech choices
   - in-scope vs out-of-scope
   - required workflows/evidence/HIL/validation rules
   - frontend console requirements
2. Produce a plan that includes:
   - **Goal statement** aligned with the “End-result goals (resume-ready)”
   - **Explicit mapping**: each plan item cites the `AUTHORITY.md` heading it satisfies
   - **Acceptance criteria** that is verifiable (e.g., evidence contracts, validation outcomes, UI pages present)
3. If any plan item would change scope/semantics:
   - propose a **minimal diff** to `AUTHORITY.md` and apply it first

## Plan format (required)
When you write a plan, use this structure:

- **Objective**: one sentence
- **Authority alignment**: bullet list of `AUTHORITY.md` headings this work implements
- **Execution steps**: 3–10 bullets, each with:
  - what changes (files/components)
  - why (tie back to authority requirement)
  - success criteria
- **Risk & guardrails**: what could go wrong + how policy/HIL/validation prevents it

## Anti-drift checklist (run before starting implementation)
- [ ] I read `AUTHORITY.md` this session.
- [ ] My plan does not add new subsystems beyond what `AUTHORITY.md` allows.
- [ ] I did not introduce “chat UI” behavior (frontend is an ops console).
- [ ] Any new job type has an evidence contract and validation path.
- [ ] Any new write action is covered by policy + (optional) HIL.

## Examples

### Example: adding a new job type
**User**: “Add a GitHub labeler agent.”

**Correct response behavior**:
- Check `AUTHORITY.md` agent list and evidence contracts.
- If label operations are not listed:
  - update `AUTHORITY.md` to add the job type (e.g., `github.add_labels`) and define evidence/minimum validation checks.
- Plan references:
  - “Multi-agent system design”
  - “Evidence contracts”
  - “Human-in-the-loop (HIL) and policy engine”
  - “Frontend → Agents / Runs / Validation Reports”


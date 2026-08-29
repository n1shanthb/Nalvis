---
name: batched-conventional-commits
description: Stage and commit changes in logical batches (not all at once) when the user says commit. Uses one-line conventional prefixes (feat:, fix:, chore:, docs:) and writes human-sounding messages with a small typo rate (~10%) without losing clarity.
---

# Batched Conventional Commits

## Trigger
Use this skill when the user says: **commit**, **/commit**, “make a commit”, “create commits”, or asks to “stage and commit”.

## Non-negotiables
- **Do not stage everything at once.** Split work into batches by feature/bugfix/docs/refactor/tooling.
- **No interactive git modes** (`git add -i`, `git rebase -i`).
- **No destructive git ops** (no hard resets, no force-push) unless explicitly requested.
- **Never commit secrets** (`.env`, credentials, tokens). Warn and exclude if present.
- **One-line commit subjects only**, using exactly one of:
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`
  - `docs: ...`

## Workflow (required)
1. Inspect repo state (run in parallel where possible):
   - `git status`
   - `git diff`
   - `git diff --staged`
   - `git log -5 --oneline` (to match local style)
2. Propose **batches**:
   - Group files by why they changed, not by directory alone.
   - Each batch should be reviewable and independently valuable.
   - If a file spans multiple concerns, prefer splitting into separate commits only if it’s clean and safe.
3. For each batch:
   - Stage **only** files in that batch (explicit paths).
   - Verify with `git diff --staged`.
   - Commit with a one-line message.
4. End with `git status` to confirm clean/staged remainder and report what’s left.

## How to choose commit type
- `feat:` new capability / new behavior
- `fix:` bug fix or correctness
- `docs:` documentation-only changes
- `chore:` tooling, configs, deps, formatting, maintenance that doesn’t change product behavior

## Commit message rules (human, but clear)
- **One line only** (no body).
- Start with the prefix + a concise verb phrase.
- Mention the “why” if it fits in one line.
- **Human vibe**: introduce small imperfections about ~10% of the time:
  - a minor typo (1 word) OR slightly informal phrasing
  - never misspell key identifiers (package names, commands, file paths)
  - never make it confusing or unprofessional

Examples (acceptable):
- `feat: add per-workspace policy toggles`
- `fix: handle missing evidence in validator`
- `docs: explain Temporal workflow semantics`
- `chore: wire up redis cache for rate limits`
- (occasional human) `fix: stop double-creating jira tickets`
- (occasional human) `feat: add agents page with success metrics`

Examples (not acceptable):
- multi-line messages
- prefixes outside the allowed set (no `refactor:`, `test:`, etc.)
- “wip”, “tmp”, or vague messages like “updates”
- typos in identifiers: `temproal`, `postgre`, `githb`

## Batching guidance
Prefer these batch boundaries:
- **Docs vs code** separate
- **Infra/tooling** (`chore`) separate from product behavior (`feat`/`fix`)
- **Frontend vs backend** separate unless they are inseparable for a single feature
- **Schema/migrations** separate if they can safely stand alone

If there are many unrelated changes, create multiple commits rather than one mega commit.


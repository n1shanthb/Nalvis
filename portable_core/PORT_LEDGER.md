# PORT_LEDGER — Phase 0A portable_core

Source: `legacy_harvest/`  
Destination: `portable_core/`  
Boundary: no `aip.main`, `aip.app_context`, `aip.inbound.*`, `aip.persistence.*`

## Accepted (copied as-is or with minimal package inits)

### Contracts
- `src/aip/contracts/*` — AgentSpecification, tools protocol, LLM/runtime contracts

### Guardrails (decision logic only)
- `action.py`, `decisions.py`, `engine.py`, `errors.py`, `identity.py`, `models.py`
- Why: pure deterministic policy evaluation; no DB

### Validation (pure slices)
- `claims.py` — claim extraction from tool_events
- `verify_github.py`, `verify_gmail.py` — live re-query helpers (depend on integrations/tools)

### Webhooks (catalog seeds + match)
- `models.py`, `github_inventory.py`, `jira_inventory.py`, `gmail_inventory.py`, `match.py`
- Why: deterministic inventory/matching without persistence

### Integrations
- `github_app.py`, `gmail_oauth.py` — auth helpers (need `aip.config`)

### Connectors (seed/live wrappers)
- `connected_systems/providers/github.py` — MCP GitHub provider + seed tools
- `connected_systems/providers/calendar.py` — native calendar provider
- `tools/calendar.py` — native Calendar REST tools

## Rewritten for portability (accepted after surgery)

| Module | Change |
|--------|--------|
| `validation/models.py` | Added Authority verdict surface |
| `validation/verdicts.py` | **NEW** — maps legacy → `PASS`/`FAIL`/`NO_EVIDENCE` |
| `validation/evidence.py` | In-memory store (no `app_context`) |
| `validation/engine.py` | Pure `validate_after_run` (no DB upsert / spec loader) |
| `validation/guardrail_bypass.py` | Injectable approval checker (no `app_context`) |
| `webhooks/catalog.py` | In-memory catalog (no SQLModel) |
| `webhooks/bind.py` | Uses `DEFAULT_COMPANY_ID` (no `aip.projects`) |
| `tools/gmail.py` | In-memory watch store (no `aip.gmail.store`) |
| `tools/base.py` | **NEW** `NativeTool` |
| `tools/registry.py` | Copied; works with portable base |
| `connected_systems/models.py` | **NEW** (missing from harvest) |
| `connected_systems/protocol.py` | **NEW** provider protocol |
| `connected_systems/presets.py` | Pure MVP presets (no SQL registry) |
| `connected_systems/providers/jira.py` | Seed-only MCP provider (no persistence) |
| `connected_systems/providers/generic_mcp.py` | Uses `McpEndpointConfig` dataclass (no `McpServerRow`) |
| `config.py` | **NEW** pydantic-settings stub |
| `interfaces/*` | **NEW** stable ports for clean rebuild |

## Rejected (do not port — stay in `legacy_harvest`)

| Path | Offending dependency / reason |
|------|-------------------------------|
| `guardrails/store.py` | `aip.persistence.db` |
| `guardrails/middleware.py` | `aip.app_context` |
| `validation/store.py` | `aip.persistence.db` |
| `validation/response_watch.py` | `aip.app_context` + watch loops |
| legacy `validation/evidence.py` / `engine.py` | `aip.app_context` (replaced by rewrites) |
| legacy `webhooks/catalog.py` | SQLModel + `aip.persistence` (replaced) |
| `connected_systems/registry.py` | SQLModel + `aip.persistence` (replaced by `presets.py`) |
| legacy `connected_systems/providers/jira.py` | persistence coupling (replaced seed provider) |
| `*_router.py`, `web/api_*.py`, `web/tunnel.py`, `runtime/*` | FastAPI ingress / orchestration — rebuild cleanly |
| `frontend/**` | Out of Phase 0A backend+connectors scope |

## Deferred (next phases)

1. Temporal orchestration replacing inbound job loops
2. Postgres-backed policy/approval/validation stores
3. Live Jira MCP execute path (beyond seed discovery)
4. Cloudflared tunnel + webhook ingress (API layer)
5. Frontend ops console
6. Full agent runtime (`execute_spec` / OpenAI Agents adapter)

## Verification

- Contract tests: `portable_core/tests/test_portable_core.py` — **12 passed**
- Forbidden-import static scan included in tests
- Public validation contract: `PASS` / `FAIL` / `NO_EVIDENCE` via `to_authority_verdict`

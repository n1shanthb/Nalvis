# Connectors + tunnel (live verification)

Goal: prove this repo can **read/write** GitHub, Jira, Gmail, and Calendar the same way legacy did:
- **GitHub / Jira** → MCP (+ GitHub REST App helpers for smoke evidence)
- **Gmail / Calendar** → native Google REST + OAuth
- **Inbound** → FastAPI webhooks + **cloudflared** quick tunnel

## Prerequisites
1. Copy `.env.example` → `.env` and fill secrets.
2. Install deps:
   ```bash
   pip install -e "./portable_core[dev]"
   pip install -e ".[dev,agents]"
   ```
   (`portable_core/src` is on `PYTHONPATH` via pytest; for runtime, install both editables.)
3. Optional: install `cloudflared` on PATH.

## Run API + tunnel
```bash
uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```
In another shell / via API:
```bash
curl -X POST http://127.0.0.1:8000/api/tunnel/start
curl http://127.0.0.1:8000/api/tunnel
```
Point provider webhooks at the returned `urls.github` / `urls.jira` / `urls.gmail`.

## Live smoke (creates real artifacts)
```bash
python scripts/smoke_connectors.py --health
python scripts/smoke_connectors.py --systems github
python scripts/smoke_connectors.py --systems jira
python scripts/smoke_connectors.py --systems gmail,calendar
```

Required env for writes:
- GitHub: `GITHUB_TOKEN` or App vars + `SMOKE_GITHUB_OWNER` / `SMOKE_GITHUB_REPO`
- Jira: `ATLASSIAN_MCP_TOKEN` + `SMOKE_JIRA_PROJECT_KEY`
- Gmail/Calendar: `GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN/USER`

## Evidence contract
Smoke results must include machine-checkable IDs/URLs (issue URL, message_id, event_id, etc.) matching `AUTHORITY.md`.

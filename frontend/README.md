# AgentSuite Frontend

Operations console UI for AgentSuite (Authority-defined pages).

**Locked UI rule:** the local store starts **empty**. There is no seeded/synthetic tenant data. Empty and error states are intentional.

## Stack

- React 19 + Vite + TypeScript
- Tailwind CSS v4
- shadcn-style primitives
- Zustand local store + `DemoAdapter` (empty in-memory) / `HttpAdapter` (future API)

## Scripts

```bash
npm install
npm run dev
npm run test
npm run typecheck
npm run build
```

## Adapter mode

- Default: empty local `DemoAdapter` (no fake runs/agents)
- Future API: `VITE_API_MODE=http` → `HttpAdapter` against `/api`

## Pages

- `/context` — company KG ingest (blank until you paste/upload)
- `/projects` — product projects (empty until control plane creates them)
- `/projects/:id/...` — runs, approvals, policies, validation, agents
- `/integrations` — live GitHub/Jira/Gmail/Calendar health + config from `/api/integrations/health`

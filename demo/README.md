# Demo KG files

Upload these in **Context Studio** (`http://localhost:5173/context`) — use **Upload** for large files, not paste.

## `nexus-digital-enterprise-kg.json`

Fictional enterprise company **Nexus Digital Inc.** (~1,200 employees) with **two product workspaces**:

| Workspace | Description |
|-----------|-------------|
| **Nexus Pay** | Payment gateway — PCI-DSS, EKS, ledger RDS |
| **Nexus Portal** | B2B customer portal — billing, CloudFront, Lambda edge |

**Systems in the graph**

| System | In graph | Executable in v1 |
|--------|----------|------------------|
| GitHub | 5 repos | Yes (MCP) |
| Jira | PAY + PORT projects | Yes (MCP) |
| Gmail | Lists + inbound threads | Yes (native) |
| Google Calendar | Sprint / release / QBR | Yes (native) |
| Slack | 5 channels | Discovery only |
| Notion | 4 pages (runbooks, RFCs) | Discovery only |
| AWS | 8 resources (EKS, RDS, S3, Lambda) | Discovery only |

**Attention items** (`need_attention: true`) — good for testing agent synthesis and inbound routing:

- SEV-2 Slack thread + Jira PAY-1847 + hotfix PR #418 (Nexus Pay)
- Enterprise billing dispute email (Nexus Portal)
- PCI audit evidence request (Nexus Pay)
- EKS pod restart incident (AWS)

## Ingest

1. Start API + worker + Docker (see `docs/SETUP.md`).
2. Open Context Studio → **Upload** → select `demo/nexus-digital-enterprise-kg.json`.
3. Expect **2 workspaces**: Nexus Pay, Nexus Portal.
4. Check **Agents** per workspace for synthesized specializations (GitHub, Jira, Gmail, Calendar agents + unsupported stubs for Slack/Notion/AWS).

To map GitHub writes to your smoke repo, edit repo slugs in the JSON before upload or rely on `SMOKE_GITHUB_APP_REPO` allowlist at runtime.

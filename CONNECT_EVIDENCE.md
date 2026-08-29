# Live connector evidence

Verified from this repo (agentsuite) with real external side effects.

## GitHub MCP (+ App token for MCP auth)
- Status: PASS
- MCP `list_tools`: OK (`issue_write` present)
- MCP write evidence: https://github.com/n1shanthb/analytics-resume/issues/5
- App REST write also verified earlier: issues #3 / #4

## Jira MCP
- Status: PASS
- Tool: `createJiraIssue` with `cloudId`
- Evidence: `SCRUM-2` (`id=10033`) via Atlassian MCP

## Native Gmail
- Status: PASS
- Evidence examples: `message_id=1a04d0afb982d4c4` (and prior `1a04d05fc574da14`)

## Native Calendar
- Status: PASS
- Evidence examples: `event_id=rbn3iq78roa683roapinr3ojg0` (and prior `9f4h769dbjbgeuv80i66oh3g80`)

## Cloudflared tunnel + webhook ingress
- Status: PASS
- `cloudflared` binary found; quick tunnel issued public `*.trycloudflare.com` URL
- Webhook paths exposed for github/jira/gmail
- Signed GitHub webhook POST accepted (`issues.opened`) and stored in delivery log

## How to re-run
```bash
python scripts/smoke_connectors.py --health
python scripts/smoke_connectors.py --systems github,jira,gmail,calendar
python scripts/_tunnel_webhook_proof.py
```

# AgentSuite — two-minute hackathon demo

Status: approved by the user on 2026-10-17 ("ok go"); rendered and verified, ready for first-cut review.
Format: 1920×1080, 16:9 MP4; English local Piper narration; readable pill captions; light AgentSuite UI with blue accents. Target 120 seconds, never longer than two minutes.
Audience: hackathon judges. Product walkthrough with a concise engineering explanation.

## Scene-by-scene script

1. **00:00–00:10 · Hook · narrated title card / still**
   Visual: AgentSuite title over the actual operations console.
   Narration: “Hi, this is AgentSuite. We help engineering and operations teams turn company context into governed work. Let me show you the product, then the architecture.”
2. **00:10–00:18 · Orient · app clip**
   Visual: Operations console; graph, agent workspace and timeline.
   Narration: “This is our operations console. Company context, specialized agents, and the execution timeline come together in one place.”
3. **00:18–00:30 · Ground the work · app clip**
   Visual: Context Studio's existing parse preview; pan to derived workspaces. Do not re-ingest.
   Narration: “We start with a company knowledge graph. Here, the ingested context becomes product workspaces, with repositories, Jira projects, and calendars defining each workspace's scope.”
4. **00:30–00:42 · Discover specialists · app clip**
   Visual: Agents directory and GitHub PR Reviewer profile, mission and tool allowlist.
   Narration: “From that context, AgentSuite discovers specialist agents. Open the GitHub PR Reviewer: its mission and tool access are explicit, so you can inspect what it is allowed to do.”
5. **00:42–00:52 · Govern actions · app still with zoom**
   Visual: Policies table highlighting GitHub review PR and its enabled HIL control. No setting changes.
   Narration: “Before execution, policy sets the boundary. This PR review action requires human approval. Permissions and approval requirements are visible to the operator.”
6. **00:52–01:08 · Show the recorded execution · app clip**
   Visual: Existing PR run, Director routing event, human approval pause, approval, execution. Clearly label recorded run using its actual date.
   Narration: “Now follow a recorded run. A GitHub pull request event reached the Director, which selected the review job. The timeline shows the approval pause, the human decision, and execution.”
7. **01:08–01:24 · Prove the outcome · app clip / evidence zoom**
   Visual: Validation report val-c39145c2496e; evidence_contract, pr_exists, review_exists, review ID.
   Narration: “Here's my favorite part: success has to come with proof. The validator checked the evidence contract, confirmed the pull request existed, and confirmed the review existed. Those checks produced the recorded PASS.”
8. **01:24–01:44 · Explain the engineering · authored architecture graphic**
   Visual: Clearly labeled architecture diagram, separate from the app: React → FastAPI → Temporal → workers / OpenAI Agents SDK → connectors. PostgreSQL and Redis roles. Show retries, approval signals and idempotent writes as design properties, not a filmed failure test.
   Narration: “Under the hood, React talks to FastAPI. Temporal coordinates workflows and approval signals, while workers run agents through the OpenAI Agents SDK. PostgreSQL stores operational records; Redis coordinates rate limits. Retries and idempotency support reliable execution.”
9. **01:44–01:52 · Make limits clear · app still with zoom**
   Visual: Unsupported Slack agent, blocked status and empty tool allowlist.
   Narration: “Discovery also makes limits visible. This Slack opportunity is marked unsupported. It stays blocked until a connector is available.”
10. **01:52–02:00 · Close · narrated outro card**
    Visual: AgentSuite; Context → Governed work → Verified outcome. No invented public product URL.
    Narration: “That's AgentSuite: company context becomes governed work, with evidence you can inspect. Start with one workflow, and verify every outcome.”

## Capture coverage and constraints

- FOUND: Operations console `/ops`, heading “Operations console”; real persisted graph, agents and completed runs.
- FOUND: `/context`, heading “Context Studio”; existing parse preview and two derived workspaces.
- FOUND: `/projects/ws-nexus-pay/agents`, heading “Nexus Pay · Agents”; GitHub PR Reviewer and unsupported Slack opportunity.
- FOUND: `/projects/ws-nexus-pay/policies`, heading “Nexus Pay · Policies”; `github.review_pr` HIL enabled.
- FOUND: `/projects/ws-nexus-pay/runs/20af7c31-3748-46dc-a1e9-72f7d1177f9e`; recorded GitHub PR #2 workflow, Director route, approval and execution events.
- FOUND: `/projects/ws-nexus-pay/validation`, heading “Nexus Pay · Validation”; report `val-c39145c2496e`, PR existence and review existence checks.
- Architecture graphic is explanatory, sourced from AUTHORITY.md “Canonical architecture”, “Temporal orchestration”, “Human-in-the-loop (HIL) and policy engine”, and “Evidence contracts”. It is not simulated product UI.
- Review and validation are recorded history from 2026-09-02, not newly executed during filming.
- No claim of a live crash/recovery test, universal success rate, or healthy four-connector deployment. Current console reports 3/4 connectors.
- Blur email addresses and secrets if they appear; retain the non-secret review ID and check names that prove the recorded result.
- Read-only capture: do not start new external jobs, send messages, re-ingest context, approve actions, or change policy.
- No new multi-system workflow or unsupported execution is staged for the video.
- Out of scope: full integration setup, every agent specialization, live external side effects, vertical/GIF variants.

## Local production assets

UltraDemo workspace: `E:\agentsuite\demo\ultrademo-workspace`
Project: `projects/agentsuite-hackathon-2026-10-17-1200`
Scouting screenshots and route evidence: project `scout/`.
Free offline voice: Piper `en_US-lessac-medium`.
Pipeline dependencies are lockfile-exact from upstream. Local compatibility adjustment removes the obsolete Piper `--download-dir` synthesis flag; download the model separately.

## Review gates

Approve or edit this script before capture. The first rendered MP4 will be presented with scene check frames for review, as required by UltraDemo.

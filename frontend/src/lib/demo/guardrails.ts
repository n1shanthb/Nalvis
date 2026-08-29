import type {
  Agent,
  AgentGuardrail,
  AgentOriginEvidence,
  AgentSpecs,
  ContextDocument,
  GuardrailMode,
  Workspace,
} from './models'

/** Stable string hash for deterministic per-agent variety (not crypto). */
function hashStr(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function pick<T>(items: T[], seed: number, count: number): T[] {
  if (items.length === 0 || count <= 0) return []
  const out: T[] = []
  let x = seed || 1
  const pool = [...items]
  while (out.length < count && pool.length > 0) {
    x = (Math.imul(x, 1103515245) + 12345) >>> 0
    const idx = x % pool.length
    out.push(pool.splice(idx, 1)[0]!)
  }
  return out
}

function defaultModeForTool(tool: string, seed: number): GuardrailMode {
  const writeish =
    /send|create|transition|review|label|merge|write|delete|schedule|create_event|add_/.test(tool)
  const readish = /get_|list_|read|search/.test(tool)
  const bucket = seed % 5
  if (!writeish && readish) return 'allow'
  if (/merge|send/.test(tool)) return bucket === 0 ? 'deny' : 'hil'
  if (writeish) {
    if (bucket <= 1) return 'hil'
    if (bucket === 2) return 'auto'
    if (bucket === 3) return 'deny'
    return 'hil'
  }
  return 'allow'
}

function modeLabel(mode: GuardrailMode): string {
  switch (mode) {
    case 'allow':
      return 'Allow'
    case 'hil':
      return 'Require HIL'
    case 'deny':
      return 'Deny'
    case 'auto':
      return 'Auto-run'
  }
}

/**
 * Synthesize agent-specific guardrails from ingested KG + tool scope.
 * Each agent gets a *different* rule set — derived from identity, tools, and workspace signals.
 */
export function synthesizeGuardrails(input: {
  agentId: string
  role: string
  toolScope: string[]
  workspaces: Workspace[]
  context?: ContextDocument | null
}): AgentGuardrail[] {
  const { agentId, role, toolScope, workspaces, context } = input
  const seed = hashStr(agentId + role + toolScope.join(','))
  const now = context?.parsedAt ?? new Date().toISOString()
  const repos = workspaces.flatMap((w) => w.scope.repos)
  const jira = workspaces.flatMap((w) => w.scope.jiraKeys)
  const emails = workspaces.flatMap((w) => w.scope.emailGroups)
  const cals = workspaces.flatMap((w) => w.scope.calendars)

  const rules: AgentGuardrail[] = []
  let i = 0

  for (const tool of toolScope) {
    const mode = defaultModeForTool(tool, seed + i * 17)
    const scopedHint =
      tool.startsWith('github') && repos.length
        ? `Limited to ${pick(repos, seed + i, Math.min(2, repos.length)).join(', ')}`
        : tool.startsWith('jira') && jira.length
          ? `Projects: ${pick(jira, seed + i, jira.length).join(', ')}`
          : tool.startsWith('gmail') && emails.length
            ? `Mailboxes: ${pick(emails, seed + i, Math.min(2, emails.length)).join(', ')}`
            : tool.startsWith('calendar') && cals.length
              ? `Calendars: ${pick(cals, seed + i, Math.min(2, cals.length)).join(', ')}`
              : 'Tenant least-privilege boundary'

    rules.push({
      id: `gr-${agentId}-${i}`,
      tool,
      mode,
      label: `${modeLabel(mode)} · ${tool}`,
      rationale: `${scopedHint}. Inferred from role “${role}” and KG product scopes.`,
      source: 'synthesized',
      createdAt: now,
    })
    i++
  }

  // Extra contextual rules — varied by agent hash so sets differ
  const extras: Array<Omit<AgentGuardrail, 'id' | 'createdAt' | 'source'>> = []

  if (toolScope.some((t) => t.includes('github')) && repos.some((r) => /pay|payment|settle/i.test(r))) {
    extras.push({
      tool: 'github.review_pr',
      mode: seed % 2 === 0 ? 'hil' : 'deny',
      label: 'Payments crypto path gate',
      rationale:
        'KG lists payment repos — changes under /crypto or /settlement require elevated governance.',
    })
  }
  if (toolScope.some((t) => t.includes('gmail'))) {
    extras.push({
      tool: 'gmail.send',
      mode: 'hil',
      label: 'External customer send always HIL',
      rationale: `Support mail groups ${emails.slice(0, 2).join(', ') || '(unscoped)'} — outbound mail never auto-runs.`,
    })
  }
  if (toolScope.some((t) => t.includes('calendar'))) {
    extras.push({
      tool: 'calendar.create_event',
      mode: seed % 3 === 0 ? 'deny' : 'hil',
      label: seed % 3 === 0 ? 'Block exec calendar writes' : 'Stakeholder meeting HIL',
      rationale: 'Calendar writes affect stakeholder schedules derived from KG calendars.',
    })
  }
  if (toolScope.some((t) => t.includes('jira'))) {
    extras.push({
      tool: 'jira.transition_ticket',
      mode: seed % 2 === 0 ? 'auto' : 'hil',
      label: seed % 2 === 0 ? 'Auto-transition in-scope projects' : 'Transition requires HIL',
      rationale: `Jira keys from KG: ${jira.join(', ') || 'none'} — mode varied by agent synthesis seed.`,
    })
  }
  if (/validat|auditor|evidence/i.test(role)) {
    extras.push({
      tool: '*',
      mode: 'deny',
      label: 'Validator is read-only',
      rationale: 'Validation Agent must never perform write actions — evidence collection only.',
    })
  }
  if (context?.parsePreview?.stakeholders?.length) {
    const stake = pick(context.parsePreview.stakeholders, seed, 1)[0]
    if (stake && toolScope.some((t) => /send|create_event|transition/.test(t))) {
      extras.push({
        tool: toolScope.find((t) => /send|create_event|transition/.test(t)) ?? toolScope[0]!,
        mode: 'hil',
        label: `Escalate when ${stake} is implicated`,
        rationale: `Stakeholder “${stake}” appears in ingested context — high-visibility actions need HIL.`,
      })
    }
  }

  // Pick 1–3 extras uniquely for this agent
  const extraCount = 1 + (seed % 3)
  for (const ex of pick(extras, seed ^ 0x9e3779b9, Math.min(extraCount, extras.length))) {
    rules.push({
      id: `gr-${agentId}-x${i}`,
      ...ex,
      source: 'synthesized',
      createdAt: now,
    })
    i++
  }

  return rules
}

export function buildOriginEvidence(input: {
  agentId: string
  role: string
  mission: string
  workspaces: Workspace[]
  context?: ContextDocument | null
}): AgentOriginEvidence {
  const { agentId, role, mission, workspaces, context } = input
  const seed = hashStr(agentId)
  const products = workspaces.map((w) => w.product)
  const repos = workspaces.flatMap((w) => w.scope.repos)
  const signals: string[] = []

  if (repos.length) signals.push(`Repos in scope: ${pick(repos, seed, Math.min(3, repos.length)).join(', ')}`)
  if (workspaces.some((w) => w.scope.jiraKeys.length)) {
    signals.push(
      `Jira projects: ${workspaces.flatMap((w) => w.scope.jiraKeys).join(', ')}`,
    )
  }
  if (workspaces.some((w) => w.scope.emailGroups.length)) {
    signals.push(
      `Email groups: ${pick(
        workspaces.flatMap((w) => w.scope.emailGroups),
        seed,
        2,
      ).join(', ')}`,
    )
  }
  if (context?.parsePreview?.stakeholders?.length) {
    signals.push(`Stakeholders: ${context.parsePreview.stakeholders.join(', ')}`)
  }

  const kgPaths = [
    ...products.map((p) => `$.products[?(@.name=='${p}')]`),
    ...pick(repos, seed, Math.min(2, repos.length)).map((r) => `$.products[*].repos[?(@=='${r}')]`),
  ]

  return {
    contextDocumentId: context?.id ?? 'ctx-unknown',
    contextDocumentName: context?.name ?? 'company-context',
    rationale: `Synthesized because ingested company context implied need for “${role}” covering ${products.join(', ') || 'tenant'}. Mission: ${mission}`,
    kgPaths,
    signals,
    synthesizedAt: context?.parsedAt ?? new Date().toISOString(),
  }
}

export function buildAgentSpecs(input: {
  agentId: string
  role: string
  toolScope: string[]
}): AgentSpecs {
  const seed = hashStr(input.agentId + input.role)
  const models = ['gpt-4.1', 'gpt-4.1-mini', 'o4-mini'] as const
  return {
    runtime: 'OpenAI Agents SDK',
    modelHint: models[seed % models.length]!,
    maxConcurrency: 1 + (seed % 3),
    timeoutSec: 60 + (seed % 5) * 30,
    memoryKeys: [
      `agent:${input.agentId}:last_job`,
      `workspace:policy_snapshot`,
      ...input.toolScope.slice(0, 2).map((t) => `tool:${t}:rate`),
    ],
    inputSchema: ['run_id', 'workspace_id', 'job_type', 'requested_action'],
    outputSchema: ['status', 'evidence_refs', 'error?'],
    leastPrivilegeNote: `Tools locked to: ${input.toolScope.join(', ') || 'none'}. Write tools consult Policy Engine + HIL.`,
  }
}

export function enrichAgentProfile(
  base: Omit<Agent, 'mission' | 'origin' | 'specs' | 'guardrails'> & {
    mission: string
  },
  workspaces: Workspace[],
  context?: ContextDocument | null,
): Agent {
  const scoped = workspaces.filter((w) => base.workspaceIds.includes(w.id))
  return {
    ...base,
    origin: buildOriginEvidence({
      agentId: base.id,
      role: base.role,
      mission: base.mission,
      workspaces: scoped,
      context,
    }),
    specs: buildAgentSpecs({
      agentId: base.id,
      role: base.role,
      toolScope: base.toolScope,
    }),
    guardrails: synthesizeGuardrails({
      agentId: base.id,
      role: base.role,
      toolScope: base.toolScope,
      workspaces: scoped,
      context,
    }),
  }
}

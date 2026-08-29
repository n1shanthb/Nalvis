import type { ContextDocument, DemoState } from './models'

/** Honest empty console state — no synthetic runs, agents, or workspaces. */
export function createEmptyState(): DemoState {
  return {
    companyName: '',
    contextDocuments: [],
    workspaces: [],
    runs: [],
    jobs: [],
    timeline: [],
    approvals: [],
    policies: [],
    integrations: [],
    validations: [],
    agents: [],
  }
}

/** @deprecated Use createEmptyState — kept so call sites rename cleanly. */
export function createSeedState(): DemoState {
  return createEmptyState()
}

export function parseContextInput(raw: string, source: 'paste' | 'upload'): ContextDocument {
  const id = `ctx-${Date.now()}`
  const name = source === 'upload' ? 'uploaded-context.json' : 'pasted-context.txt'
  try {
    const data = JSON.parse(raw) as {
      company?: string
      products?: Array<{
        name: string
        repos?: string[]
        jira?: string[]
        calendars?: string[]
        email_groups?: string[]
      }>
      stakeholders?: string[]
    }
    const products = data.products ?? []
    return {
      id,
      name,
      source,
      raw,
      parsedAt: new Date().toISOString(),
      workspaceIds: products.map((p) => `ws-${p.name.toLowerCase()}`),
      parsePreview: {
        products: products.map((p) => p.name),
        workspacesDerived: products.length,
        repos: products.flatMap((p) => p.repos ?? []),
        jiraProjects: products.flatMap((p) => p.jira ?? []),
        calendars: products.flatMap((p) => p.calendars ?? []),
        emailGroups: products.flatMap((p) => p.email_groups ?? []),
        stakeholders: data.stakeholders ?? [],
        warnings: products.length === 0 ? ['No products found in payload'] : [],
      },
    }
  } catch {
    const lines = raw
      .split(/\n/)
      .map((l) => l.trim())
      .filter(Boolean)
    return {
      id,
      name,
      source,
      raw,
      parsedAt: new Date().toISOString(),
      workspaceIds: [],
      parsePreview: {
        products: [],
        workspacesDerived: 0,
        repos: lines.filter((l) => l.includes('/')),
        jiraProjects: [],
        calendars: lines.filter((l) => l.includes('@') && l.includes('calendar')),
        emailGroups: lines.filter((l) => l.includes('@')),
        stakeholders: [],
        warnings: [
          'Input was not valid JSON — used heuristic text parse',
          lines.length === 0 ? 'Empty input' : '',
        ].filter(Boolean),
      },
    }
  }
}

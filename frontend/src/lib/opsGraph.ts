/** Build an operations knowledge graph from live control-plane state (no synthetic nodes). */

import type {
  Agent,
  IntegrationHealth,
  Workspace,
} from '@/lib/demo/models'

export type OpsNodeKind =
  | 'company'
  | 'workspace'
  | 'repo'
  | 'system'
  | 'agent'
  | 'jira'
  | 'calendar'
  | 'email'

export interface OpsGraphNode {
  id: string
  label: string
  kind: OpsNodeKind
  subtitle?: string
  href?: string
  status?: string
}

export interface OpsGraphEdge {
  id: string
  source: string
  target: string
  relation: string
}

export interface OpsGraph {
  nodes: OpsGraphNode[]
  edges: OpsGraphEdge[]
}

export function buildOpsGraph(input: {
  companyName: string
  workspaces: Workspace[]
  agents: Agent[]
  integrations: IntegrationHealth[]
}): OpsGraph {
  const nodes: OpsGraphNode[] = []
  const edges: OpsGraphEdge[] = []
  const seen = new Set<string>()

  function addNode(n: OpsGraphNode) {
    if (seen.has(n.id)) return
    seen.add(n.id)
    nodes.push(n)
  }

  function link(source: string, target: string, relation: string) {
    edges.push({
      id: `${source}->${target}:${relation}`,
      source,
      target,
      relation,
    })
  }

  const companyId = 'company'
  const companyLabel = (input.companyName || '').trim() || 'Company'
  addNode({ id: companyId, label: companyLabel, kind: 'company', subtitle: 'tenant' })

  for (const integ of input.integrations) {
    const sid = `system:${integ.name}`
    addNode({
      id: sid,
      label: integ.displayName || integ.name,
      kind: 'system',
      subtitle: integ.status,
      status: integ.status,
      href: '/integrations',
    })
    link(companyId, sid, 'uses')
  }

  for (const ws of input.workspaces) {
    const wid = `ws:${ws.id}`
    addNode({
      id: wid,
      label: ws.name,
      kind: 'workspace',
      subtitle: 'product workspace',
      href: `/projects/${ws.id}`,
    })
    link(wid, companyId, 'belongs_to')

    for (const repo of ws.scope.repos) {
      const rid = `repo:${repo}`
      addNode({
        id: rid,
        label: repo.includes('/') ? repo.split('/').pop()! : repo,
        kind: 'repo',
        subtitle: repo,
        href: `/projects/${ws.id}`,
      })
      link(rid, wid, 'scoped_to')
      if (seen.has('system:github')) link(rid, 'system:github', 'on')
    }

    for (const key of ws.scope.jiraKeys) {
      const jid = `jira:${key}`
      addNode({ id: jid, label: key, kind: 'jira', subtitle: 'Jira project' })
      link(jid, wid, 'scoped_to')
      if (seen.has('system:jira')) link(jid, 'system:jira', 'on')
    }

    for (const cal of ws.scope.calendars) {
      const cid = `cal:${ws.id}:${cal}`
      addNode({ id: cid, label: cal, kind: 'calendar', subtitle: 'calendar' })
      link(cid, wid, 'scoped_to')
      if (seen.has('system:calendar')) link(cid, 'system:calendar', 'on')
    }

    for (const em of ws.scope.emailGroups) {
      const eid = `email:${em}`
      addNode({ id: eid, label: em, kind: 'email', subtitle: 'comms' })
      link(eid, wid, 'scoped_to')
      if (seen.has('system:gmail')) link(eid, 'system:gmail', 'on')
    }

    for (const agent of input.agents.filter((a) => a.workspaceIds.includes(ws.id))) {
      const aid = `agent:${agent.id}`
      addNode({
        id: aid,
        label: agent.name.replace(`${ws.name} `, ''),
        kind: 'agent',
        subtitle: agent.role,
        status: agent.status,
        href: `/projects/${ws.id}/agents/${agent.id}`,
      })
      link(aid, wid, 'serves')
      const systemHint = agent.role.toLowerCase()
      for (const name of ['github', 'jira', 'gmail', 'calendar'] as const) {
        if (systemHint.includes(name) && seen.has(`system:${name}`)) {
          link(aid, `system:${name}`, 'uses')
        }
      }
    }
  }

  return { nodes, edges }
}

/** Deterministic layered layout for SVG (no external graph lib). */
export function layoutOpsGraph(
  graph: OpsGraph,
  width = 920,
  height = 360,
): Map<string, { x: number; y: number }> {
  const pos = new Map<string, { x: number; y: number }>()
  const byKind = (k: OpsNodeKind) => graph.nodes.filter((n) => n.kind === k)

  const layers: OpsNodeKind[][] = [
    ['company'],
    ['workspace'],
    ['system'],
    ['repo', 'jira', 'calendar', 'email'],
    ['agent'],
  ]

  // Only allocate vertical space for layers that have nodes — pack from the top.
  const activeLayers = layers
    .map((kinds, li) => ({ kinds, li, nodes: kinds.flatMap((k) => byKind(k)) }))
    .filter((l) => l.nodes.length > 0)

  const top = 28
  const bottomPad = 24
  const gap =
    activeLayers.length > 1
      ? (height - top - bottomPad) / (activeLayers.length - 1)
      : 0

  activeLayers.forEach((layer, idx) => {
    const y = top + idx * gap
    const n = layer.nodes.length
    const pad = 48
    const usable = Math.max(width - pad * 2, 100)
    layer.nodes.forEach((node, i) => {
      const x = pad + (usable * (i + 0.5)) / n
      pos.set(node.id, { x, y })
    })
  })

  for (const node of graph.nodes) {
    if (!pos.has(node.id)) {
      pos.set(node.id, { x: width / 2, y: height - 20 })
    }
  }

  return pos
}

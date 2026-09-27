import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  buildOpsGraph,
  layoutOpsGraph,
  type OpsGraphNode,
  type OpsNodeKind,
} from '@/lib/opsGraph'
import type { Agent, IntegrationHealth, Workspace } from '@/lib/demo/models'
import { cn } from '@/lib/utils'

const KIND_COLOR: Record<OpsNodeKind, string> = {
  company: '#2563eb',
  workspace: '#0891b2',
  system: '#7c3aed',
  repo: '#059669',
  jira: '#d97706',
  calendar: '#db2777',
  email: '#ea580c',
  agent: '#0f172a',
}

export function KnowledgeGraphPanel({
  companyName,
  workspaces,
  agents,
  integrations,
}: {
  companyName: string
  workspaces: Workspace[]
  agents: Agent[]
  integrations: IntegrationHealth[]
}) {
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const graph = useMemo(
    () => buildOpsGraph({ companyName, workspaces, agents, integrations }),
    [companyName, workspaces, agents, integrations],
  )

  const q = filter.trim().toLowerCase()
  const visibleIds = useMemo(() => {
    if (!q) return new Set(graph.nodes.map((n) => n.id))
    const hits = new Set(
      graph.nodes
        .filter(
          (n) =>
            n.label.toLowerCase().includes(q) ||
            (n.subtitle || '').toLowerCase().includes(q) ||
            n.kind.includes(q),
        )
        .map((n) => n.id),
    )
    for (const e of graph.edges) {
      if (hits.has(e.source) || hits.has(e.target)) {
        hits.add(e.source)
        hits.add(e.target)
      }
    }
    return hits
  }, [graph, q])

  const width = 920
  const height = 340
  const pos = useMemo(() => layoutOpsGraph(graph, width, height), [graph])

  const selectedNode = graph.nodes.find((n) => n.id === selected)

  if (graph.nodes.length <= 1) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
        <p className="text-sm font-medium text-[var(--color-fg)]">No knowledge graph yet</p>
        <p className="mt-1 max-w-sm text-xs text-[var(--color-muted)]">
          Ingest company KG JSON in Context Studio to populate workspaces, scopes, and agents.
        </p>
        <Link
          to="/context"
          className="mt-3 text-sm text-[var(--color-accent)] hover:underline"
        >
          Open Context Studio →
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--color-border)] px-3 py-2">
        <div className="text-sm font-semibold text-[var(--color-fg)]">Company knowledge graph</div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search graph…"
            className="h-8 w-44 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-2 text-xs outline-none focus:border-[var(--color-accent)]"
            aria-label="Search graph"
          />
          <span className="text-[11px] text-[var(--color-muted)]">
            {graph.nodes.length} nodes · {graph.edges.length} edges
          </span>
        </div>
      </div>

      <div className="relative overflow-hidden bg-[radial-gradient(circle_at_1px_1px,#d8e0ea_1px,transparent_0)] [background-size:16px_16px]">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMin meet"
          className="block h-[340px] w-full"
          role="img"
          aria-label="Company knowledge graph"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>

          {graph.edges.map((e) => {
            if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) return null
            const a = pos.get(e.source)
            const b = pos.get(e.target)
            if (!a || !b) return null
            const midX = (a.x + b.x) / 2
            const midY = (a.y + b.y) / 2
            return (
              <g key={e.id} opacity={selected && selected !== e.source && selected !== e.target ? 0.2 : 0.85}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="#94a3b8"
                  strokeWidth={1.25}
                  markerEnd="url(#arrow)"
                />
                <text
                  x={midX}
                  y={midY - 4}
                  textAnchor="middle"
                  className="fill-[var(--color-muted)]"
                  style={{ fontSize: 8 }}
                >
                  {e.relation}
                </text>
              </g>
            )
          })}

          {graph.nodes.map((node) => {
            if (!visibleIds.has(node.id)) return null
            const p = pos.get(node.id)
            if (!p) return null
            return (
              <GraphNode
                key={node.id}
                node={node}
                x={p.x}
                y={p.y}
                active={selected === node.id}
                dimmed={Boolean(selected && selected !== node.id)}
                onSelect={() => setSelected((s) => (s === node.id ? null : node.id))}
              />
            )
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--color-border)] px-3 py-1.5 text-[11px] text-[var(--color-muted)]">
        <span>
          <strong className="text-[var(--color-fg)]">{workspaces.length}</strong> workspaces
        </span>
        <span>
          <strong className="text-[var(--color-fg)]">
            {graph.nodes.filter((n) => n.kind === 'repo').length}
          </strong>{' '}
          repos
        </span>
        <span>
          <strong className="text-[var(--color-fg)]">{agents.length}</strong> agents
        </span>
        {selectedNode ? (
          <span className="ml-auto truncate text-[var(--color-fg-dim)]">
            Selected: {selectedNode.label}
            {selectedNode.href ? (
              <>
                {' · '}
                <Link to={selectedNode.href} className="text-[var(--color-accent)] hover:underline">
                  open
                </Link>
              </>
            ) : null}
          </span>
        ) : (
          <span className="ml-auto">Click a node for details</span>
        )}
      </div>
    </div>
  )
}

function GraphNode({
  node,
  x,
  y,
  active,
  dimmed,
  onSelect,
}: {
  node: OpsGraphNode
  x: number
  y: number
  active: boolean
  dimmed: boolean
  onSelect: () => void
}) {
  const color = KIND_COLOR[node.kind]
  const w = node.kind === 'company' ? 132 : node.kind === 'workspace' ? 118 : 108
  const h = node.kind === 'agent' || node.kind === 'company' ? 42 : 36

  return (
    <g
      transform={`translate(${x - w / 2}, ${y - h / 2})`}
      opacity={dimmed ? 0.25 : 1}
      className="cursor-pointer"
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onSelect()
      }}
    >
      <rect
        width={w}
        height={h}
        rx={8}
        fill="#ffffff"
        stroke={active ? color : '#d8e0ea'}
        strokeWidth={active ? 2.5 : 1.25}
        className={cn(active && 'drop-shadow')}
      />
      <rect x={0} y={0} width={4} height={h} rx={2} fill={color} />
      <text x={12} y={15} style={{ fontSize: 10, fontWeight: 600 }} fill="#0f172a">
        {truncate(node.label, 16)}
      </text>
      <text x={12} y={28} style={{ fontSize: 8 }} fill="#64748b">
        {truncate(node.subtitle || node.kind, 18)}
      </text>
    </g>
  )
}

function truncate(s: string, n: number) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}

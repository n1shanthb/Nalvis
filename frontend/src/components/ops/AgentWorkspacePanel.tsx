import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { agentDisplayName, formatPercent, formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'
import type { Agent, Workspace } from '@/lib/demo/models'

export function AgentWorkspacePanel({
  agents,
  workspaces,
}: {
  agents: Agent[]
  workspaces: Workspace[]
}) {
  const getAgentMetrics = useDemoStore((s) => s.getAgentMetrics)
  const jobs = useDemoStore((s) => s.jobs)

  if (agents.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center text-sm text-[var(--color-muted)]">
        No agents yet — ingest a company KG to synthesize specialists.
      </div>
    )
  }

  const sorted = [...agents].sort((a, b) => {
    const rank = (s: string) => (s === 'active' ? 0 : s === 'idle' ? 1 : s === 'unsupported' ? 3 : 2)
    return rank(a.status) - rank(b.status) || a.name.localeCompare(b.name)
  })

  return (
    <div className="flex max-h-[420px] flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="border-b border-[var(--color-border)] px-3 py-2">
        <div className="text-sm font-semibold">Agent workspace</div>
        <p className="mt-0.5 text-[11px] text-[var(--color-muted)]">
          Live specialists — metrics from validations
        </p>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {sorted.map((agent) => {
          const metrics = getAgentMetrics(agent.id)
          const totalVal =
            metrics.overall.PASS + metrics.overall.FAIL + metrics.overall.NO_EVIDENCE
          const passRate = totalVal ? metrics.overall.PASS / totalVal : null
          const ws = workspaces.find((w) => agent.workspaceIds.includes(w.id))
          const recentJobs = jobs.filter((j) => j.agentId === agent.id).length
          const statusVariant =
            agent.status === 'active'
              ? 'pass'
              : agent.status === 'unsupported'
                ? 'warn'
                : agent.status === 'error'
                  ? 'fail'
                  : 'default'

          return (
            <Link
              key={agent.id}
              to={ws ? `/projects/${ws.id}/agents/${agent.id}` : '/projects'}
              className="block rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/60 p-3 transition-colors hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-bg)]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-[var(--color-fg)]">
                    {agentDisplayName(agent.name, ws?.name)}
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[10px] text-[var(--color-muted)]">
                    {agent.role}
                  </div>
                </div>
                <Badge variant={statusVariant}>{agent.status}</Badge>
              </div>

              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[var(--color-fg-dim)]">
                <span>
                  Last active{' '}
                  <span className="text-[var(--color-muted)]">
                    {agent.lastActiveAt ? formatRelative(agent.lastActiveAt) : 'never'}
                  </span>
                </span>
                <span>
                  Model{' '}
                  <span className="font-mono text-[var(--color-muted)]">
                    {agent.specs?.modelHint || 'catalog'}
                  </span>
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {passRate != null ? (
                  <span className="rounded bg-[var(--color-pass)]/10 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-pass)]">
                    PASS {formatPercent(passRate)}
                  </span>
                ) : (
                  <span className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] text-[var(--color-muted)]">
                    No validations yet
                  </span>
                )}
                {metrics.overall.NO_EVIDENCE > 0 ? (
                  <span className="rounded bg-[var(--color-warn)]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-warn)]">
                    NO_EVIDENCE {metrics.overall.NO_EVIDENCE}
                  </span>
                ) : null}
                {metrics.overall.FAIL > 0 ? (
                  <span className="rounded bg-[var(--color-fail)]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-fail)]">
                    FAIL {metrics.overall.FAIL}
                  </span>
                ) : null}
                <span className="text-[10px] text-[var(--color-muted)]">{recentJobs} jobs</span>
              </div>

              {ws ? (
                <div className="mt-2 truncate text-[10px] text-[var(--color-muted)]">{ws.name}</div>
              ) : null}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

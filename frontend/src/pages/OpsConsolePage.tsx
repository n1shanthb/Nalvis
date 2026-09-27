import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { KnowledgeGraphPanel } from '@/components/ops/KnowledgeGraphPanel'
import { AgentWorkspacePanel } from '@/components/ops/AgentWorkspacePanel'
import { TemporalTimelinePanel } from '@/components/ops/TemporalTimelinePanel'
import { getAdapterMode } from '@/lib/api'
import { useDemoStore } from '@/lib/store'
import { formatPercent } from '@/lib/utils'

export function OpsConsolePage() {
  const hydrate = useDemoStore((s) => s.hydrate)
  const companyName = useDemoStore((s) => s.companyName)
  const workspaces = useDemoStore((s) => s.workspaces)
  const agents = useDemoStore((s) => s.agents)
  const integrations = useDemoStore((s) => s.integrations)
  const runs = useDemoStore((s) => s.runs)
  const jobs = useDemoStore((s) => s.jobs)
  const timeline = useDemoStore((s) => s.timeline)
  const validations = useDemoStore((s) => s.validations)
  const approvals = useDemoStore((s) => s.approvals)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    void hydrate()
    const id = window.setInterval(() => {
      void hydrate()
    }, 15_000)
    return () => window.clearInterval(id)
  }, [hydrate])

  const running = runs.filter((r) => r.status === 'running' || r.status === 'queued').length
  const queuedJobs = jobs.filter((j) => j.status === 'queued').length
  const blocked = jobs.filter((j) => j.status === 'blocked_for_approval').length
  const pendingHil = approvals.filter((a) => a.decision === 'pending').length
  const activeAgents = agents.filter((a) => a.status === 'active' || a.status === 'idle').length
  const unsupported = agents.filter((a) => a.status === 'unsupported').length
  const pass = validations.filter((v) => v.verdict === 'PASS').length
  const fail = validations.filter((v) => v.verdict === 'FAIL').length
  const none = validations.filter((v) => v.verdict === 'NO_EVIDENCE').length
  const valTotal = validations.length
  const healthyInteg = integrations.filter((i) => i.status === 'healthy').length

  return (
    <div className="-mx-2 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight">Operations console</h1>
            <Badge variant={getAdapterMode() === 'http' ? 'accent' : 'warn'}>
              {getAdapterMode() === 'http' ? 'ENV: LIVE' : 'ENV: LOCAL'}
            </Badge>
          </div>
          <p className="mt-0.5 text-xs text-[var(--color-muted)]">
            {companyName || 'No company loaded'} · graph · agents · Temporal timeline
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-[11px] text-[var(--color-fg-dim)]">
            <Activity className="h-3 w-3 text-[var(--color-pass)]" aria-hidden />
            System health · {healthyInteg}/{integrations.length || 0} connectors
          </div>
          <Button
            variant="secondary"
            disabled={refreshing}
            onClick={async () => {
              setRefreshing(true)
              try {
                await hydrate()
              } finally {
                setRefreshing(false)
              }
            }}
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <Stat label="Agents ready" value={`${activeAgents}/${agents.length}`} hint={`${unsupported} unsupported`} />
        <Stat label="Runs active" value={running} tone="accent" />
        <Stat label="Jobs queued" value={queuedJobs} />
        <Stat
          label="Pending HIL"
          value={pendingHil}
          tone={pendingHil ? 'warn' : 'pass'}
          hint={blocked ? `${blocked} blocked jobs` : undefined}
        />
        <Stat
          label="PASS rate"
          value={valTotal ? formatPercent(pass / valTotal) : '—'}
          tone="pass"
          hint={valTotal ? `${pass}P · ${fail}F · ${none}NE` : 'no validations'}
        />
        <Stat label="Workspaces" value={workspaces.length} hint={companyName || 'ingest KG'} />
      </div>

      {workspaces.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center">
          <p className="text-sm font-medium">Empty tenant — nothing to operate yet</p>
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            Upload a company knowledge graph to create workspaces and agents.
          </p>
          <Link to="/context" className="mt-4 inline-block text-sm text-[var(--color-accent)] hover:underline">
            Go to Context Studio →
          </Link>
        </div>
      ) : (
        <>
          <div className="grid items-start gap-3 xl:grid-cols-[1fr_300px]">
            <KnowledgeGraphPanel
              companyName={companyName}
              workspaces={workspaces}
              agents={agents}
              integrations={integrations}
            />
            <AgentWorkspacePanel agents={agents} workspaces={workspaces} />
          </div>

          <TemporalTimelinePanel
            runs={runs}
            jobs={jobs}
            timeline={timeline}
            validations={validations}
            agents={agents}
            workspaces={workspaces}
          />
        </>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: string | number
  hint?: string
  tone?: 'default' | 'pass' | 'fail' | 'warn' | 'accent'
}) {
  const tones = {
    default: 'text-[var(--color-fg)]',
    pass: 'text-[var(--color-pass)]',
    fail: 'text-[var(--color-fail)]',
    warn: 'text-[var(--color-warn)]',
    accent: 'text-[var(--color-accent)]',
  }
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${tones[tone]}`}>{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-[var(--color-muted)]">{hint}</div> : null}
    </div>
  )
}

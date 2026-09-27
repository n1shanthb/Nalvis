import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { formatRelative } from '@/lib/utils'
import type {
  Agent,
  Job,
  Run,
  TimelineEvent,
  ValidationOutcome,
  Workspace,
} from '@/lib/demo/models'

export function TemporalTimelinePanel({
  runs,
  jobs,
  timeline,
  validations,
  agents,
  workspaces,
}: {
  runs: Run[]
  jobs: Job[]
  timeline: TimelineEvent[]
  validations: ValidationOutcome[]
  agents: Agent[]
  workspaces: Workspace[]
}) {
  const latest = [...runs].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0]

  const events = latest
    ? timeline
        .filter((t) => t.runId === latest.id)
        .sort((a, b) => a.at.localeCompare(b.at))
    : []

  const runJobs = latest ? jobs.filter((j) => j.runId === latest.id) : []
  const runVals = latest ? validations.filter((v) => v.runId === latest.id) : []

  const rows = buildRows(events, runJobs, runVals, agents)

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-muted)]">
            Temporal workflow timeline
          </div>
          {latest ? (
            <div className="mt-0.5 text-sm font-medium text-[var(--color-fg)]">
              {latest.title || latest.id}
              <span className="ml-2 font-mono text-[11px] font-normal text-[var(--color-muted)]">
                {latest.temporalWorkflowId || latest.id}
              </span>
            </div>
          ) : (
            <div className="mt-0.5 text-sm text-[var(--color-muted)]">No runs yet</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {latest ? (
            <>
              <Badge
                variant={
                  latest.status === 'succeeded'
                    ? 'pass'
                    : latest.status === 'failed'
                      ? 'fail'
                      : latest.status === 'running'
                        ? 'warn'
                        : 'default'
                }
              >
                {latest.status}
              </Badge>
              {latest.workspaceIds[0] ? (
                <Link
                  to={`/projects/${latest.workspaceIds[0]}/runs/${latest.id}`}
                  className="text-xs text-[var(--color-accent)] hover:underline"
                >
                  Open run →
                </Link>
              ) : null}
              <a
                href="http://localhost:8080"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-[var(--color-muted)] hover:text-[var(--color-fg)]"
              >
                Temporal UI ↗
              </a>
            </>
          ) : null}
        </div>
      </div>

      {!latest ? (
        <div className="p-8 text-center text-sm text-[var(--color-muted)]">
          Start a company run or trigger a webhook — timeline events appear here from the control
          plane audit log.
        </div>
      ) : rows.length === 0 ? (
        <div className="p-8 text-center text-sm text-[var(--color-muted)]">
          Run exists but no timeline events yet (worker may still be processing).
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
              <tr>
                <th className="px-4 py-2 font-semibold">Time</th>
                <th className="px-4 py-2 font-semibold">Event</th>
                <th className="px-4 py-2 font-semibold">Status</th>
                <th className="px-4 py-2 font-semibold">Agent / job</th>
                <th className="px-4 py-2 font-semibold">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-[var(--color-border)]/70 last:border-0 hover:bg-[var(--color-bg)]/50"
                >
                  <td className="whitespace-nowrap px-4 py-2.5 text-[var(--color-muted)]">
                    <time dateTime={row.at}>{formatRelative(row.at)}</time>
                  </td>
                  <td className="px-4 py-2.5 font-medium text-[var(--color-fg)]">{row.event}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={row.statusVariant}>{row.status}</Badge>
                  </td>
                  <td className="max-w-[180px] truncate px-4 py-2.5 text-[var(--color-fg-dim)]">
                    {row.actor}
                  </td>
                  <td className="max-w-[280px] truncate px-4 py-2.5 font-mono text-[10px] text-[var(--color-muted)]">
                    {row.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {latest && latest.workspaceIds.length > 0 ? (
        <div className="border-t border-[var(--color-border)] px-4 py-2 text-[11px] text-[var(--color-muted)]">
          Workspaces:{' '}
          {latest.workspaceIds
            .map((id) => workspaces.find((w) => w.id === id)?.name ?? id)
            .join(', ')}
          {' · '}
          {runJobs.length} jobs · {runVals.length} validations
        </div>
      ) : null}
    </div>
  )
}

type Row = {
  id: string
  at: string
  event: string
  status: string
  statusVariant: 'pass' | 'fail' | 'warn' | 'default' | 'accent' | 'none'
  actor: string
  detail: string
}

function buildRows(
  events: TimelineEvent[],
  jobs: Job[],
  validations: ValidationOutcome[],
  agents: Agent[],
): Row[] {
  const jobById = new Map(jobs.map((j) => [j.id, j]))
  const agentById = new Map(agents.map((a) => [a.id, a]))
  const valByJob = new Map(validations.map((v) => [v.jobId, v]))

  return events.map((e) => {
    const job = e.jobId ? jobById.get(e.jobId) : undefined
    const agent = job ? agentById.get(job.agentId) : undefined
    const val = job ? valByJob.get(job.id) : undefined

    let status = e.kind.replace('_', ' ')
    let statusVariant: Row['statusVariant'] = 'default'
    if (e.kind === 'failed') {
      status = 'FAILED'
      statusVariant = 'fail'
    } else if (e.kind === 'completed') {
      status = 'COMPLETED'
      statusVariant = 'pass'
    } else if (e.kind === 'validation' && val) {
      status = val.verdict
      statusVariant =
        val.verdict === 'PASS' ? 'pass' : val.verdict === 'FAIL' ? 'fail' : 'warn'
    } else if (e.kind === 'approval') {
      status = 'HIL'
      statusVariant = 'warn'
    } else if (e.kind === 'started' || e.kind === 'tool_call') {
      statusVariant = 'accent'
    }

    const detailParts: string[] = []
    if (job) detailParts.push(job.jobType)
    if (val?.message) detailParts.push(val.message.slice(0, 80))
    if (job?.error) detailParts.push(`err: ${job.error.slice(0, 60)}`)
    if (e.meta) {
      const m = Object.entries(e.meta)
        .slice(0, 2)
        .map(([k, v]) => `${k}=${v}`)
        .join(' ')
      if (m) detailParts.push(m)
    }

    return {
      id: e.id,
      at: e.at,
      event: e.label,
      status,
      statusVariant,
      actor: agent?.name || job?.title || e.jobId || 'workflow',
      detail: detailParts.join(' · ') || e.kind,
    }
  })
}

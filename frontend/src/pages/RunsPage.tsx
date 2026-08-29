import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { FilterChips, RunStatusBadge } from '@/components/shared/status'
import { formatRelative } from '@/lib/utils'
import { useProjectData } from '@/lib/useProjectData'
import type { RunStatus } from '@/lib/demo/models'

export function RunsPage() {
  const { projectId = '' } = useParams()
  const { workspace, runs } = useProjectData(projectId)
  const [status, setStatus] = useState<RunStatus | 'all'>('all')

  const filtered = useMemo(
    () => runs.filter((r) => (status === 'all' ? true : r.status === status)),
    [runs, status],
  )

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Runs`}
        description="Orchestrated Temporal runs for this product project."
      />
      <MetricStrip
        items={[
          { label: 'Total runs', value: runs.length },
          {
            label: 'Running',
            value: runs.filter((r) => r.status === 'running').length,
            tone: 'accent',
          },
          {
            label: 'Succeeded',
            value: runs.filter((r) => r.status === 'succeeded').length,
            tone: 'pass',
          },
          {
            label: 'Failed / partial',
            value: runs.filter((r) => r.status === 'failed' || r.status === 'partial').length,
            tone: 'warn',
          },
        ]}
      />

      <div className="mb-4">
        <FilterChips
          value={status}
          onChange={setStatus}
          options={(['queued', 'running', 'succeeded', 'failed', 'partial'] as RunStatus[]).map(
            (s) => ({ value: s, label: s }),
          )}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No runs in this project" description="Adjust status filter or wait for orchestration." />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Run list</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                <tr className="border-b border-[var(--color-border)]">
                  <th className="pb-2 font-medium">Run</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Jobs</th>
                  <th className="pb-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((run) => (
                  <tr key={run.id} className="border-b border-[var(--color-border)]/60">
                    <td className="py-3">
                      <Link
                        to={`/projects/${projectId}/runs/${run.id}`}
                        className="font-medium text-[var(--color-accent)] hover:underline"
                      >
                        {run.title}
                      </Link>
                      <div className="font-mono text-[11px] text-[var(--color-muted)]">{run.id}</div>
                    </td>
                    <td className="py-3">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="py-3 tabular-nums">{run.jobIds.length}</td>
                    <td className="py-3 text-xs text-[var(--color-muted)]">
                      {formatRelative(run.updatedAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

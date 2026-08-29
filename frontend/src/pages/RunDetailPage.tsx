import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, EmptyState } from '@/components/shared/page'
import { JobStatusBadge, RunStatusBadge, VerdictBadge } from '@/components/shared/status'
import { DagPanel, Timeline } from '@/components/shared/timeline'
import { formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'

export function RunDetailPage() {
  const { projectId = '', runId = '' } = useParams()
  const run = useDemoStore((s) => s.runs.find((r) => r.id === runId))
  const jobsAll = useDemoStore((s) => s.jobs)
  const timelineAll = useDemoStore((s) => s.timeline)
  const validationsAll = useDemoStore((s) => s.validations)
  const agents = useDemoStore((s) => s.agents)
  const workspaces = useDemoStore((s) => s.workspaces)

  const jobs = useMemo(() => jobsAll.filter((j) => j.runId === runId), [jobsAll, runId])
  const timeline = useMemo(
    () =>
      timelineAll.filter((t) => t.runId === runId).sort((a, b) => a.at.localeCompare(b.at)),
    [timelineAll, runId],
  )
  const validations = useMemo(
    () => validationsAll.filter((v) => v.runId === runId),
    [validationsAll, runId],
  )

  if (!run || !run.workspaceIds.includes(projectId)) {
    return <EmptyState title="Run not found" description={`No run ${runId} in this project`} />
  }

  return (
    <div>
      <PageHeader
        title={run.title}
        description={`${run.id} · Temporal ${run.temporalWorkflowId}`}
        actions={<RunStatusBadge status={run.status} />}
      />

      <div className="mb-4 flex flex-wrap gap-3 text-xs text-[var(--color-muted)]">
        <span>Updated {formatRelative(run.updatedAt)}</span>
        <span>·</span>
        <span>
          Workspaces:{' '}
          {run.workspaceIds
            .map((id) => workspaces.find((w) => w.id === id)?.name ?? id)
            .join(', ')}
        </span>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Objectives</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--color-fg-dim)]">
            {run.objectives.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Job DAG</CardTitle>
            <CardDescription>Ordered job steps for this run.</CardDescription>
          </CardHeader>
          <CardContent>
            <DagPanel jobs={jobs} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Timeline</CardTitle>
            <CardDescription>Approvals, tool calls, and validation events.</CardDescription>
          </CardHeader>
          <CardContent>
            <Timeline events={timeline} />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Jobs</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              <tr className="border-b border-[var(--color-border)]">
                <th className="pb-2 font-medium">Job</th>
                <th className="pb-2 font-medium">Agent</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Validation</th>
                <th className="pb-2 font-medium">Links</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => {
                const val = validations.find((v) => v.jobId === job.id)
                return (
                  <tr key={job.id} className="border-b border-[var(--color-border)]/60">
                    <td className="py-3">
                      <div className="font-medium">{job.title}</div>
                      <div className="font-mono text-[11px] text-[var(--color-muted)]">
                        {job.jobType} · {job.id}
                      </div>
                    </td>
                    <td className="py-3">
                      <Link
                        className="text-[var(--color-accent)] hover:underline"
                        to={`/projects/${projectId}/agents/${job.agentId}`}
                      >
                        {agents.find((a) => a.id === job.agentId)?.name ?? job.agentId}
                      </Link>
                    </td>
                    <td className="py-3">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="py-3">
                      {val ? (
                        <Link to={`/projects/${projectId}/validation#${val.id}`}>
                          <VerdictBadge verdict={val.verdict} />
                        </Link>
                      ) : (
                        <span className="text-xs text-[var(--color-muted)]">—</span>
                      )}
                    </td>
                    <td className="py-3 text-xs">
                      {job.approvalId ? (
                        <Link
                          className="text-[var(--color-accent)] hover:underline"
                          to={`/projects/${projectId}/approvals`}
                        >
                          Approval {job.approvalId}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

import { Link, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { AgentStatusBadge } from '@/components/shared/status'
import { formatPercent, formatRelative, agentDisplayName } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import type { ValidationVerdict } from '@/lib/demo/models'

function emptyCounts(): Record<ValidationVerdict, number> {
  return { PASS: 0, FAIL: 0, NO_EVIDENCE: 0 }
}

export function AgentsPage() {
  const { projectId = '' } = useParams()
  const { workspace, agents, validations } = useProjectData(projectId)
  const getAgentMetrics = useDemoStore((s) => s.getAgentMetrics)

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Agents`}
        description="Executors assigned to this product project, with validation-backed success metrics."
      />
      <MetricStrip
        items={[
          { label: 'Agents', value: agents.length },
          {
            label: 'Active',
            value: agents.filter((a) => a.status === 'active').length,
            tone: 'pass',
          },
          {
            label: 'Idle',
            value: agents.filter((a) => a.status === 'idle').length,
          },
          {
            label: 'Unsupported',
            value: agents.filter((a) => a.status === 'unsupported').length,
            tone: 'warn',
          },
          {
            label: 'Error',
            value: agents.filter((a) => a.status === 'error').length,
            tone: 'fail',
          },
        ]}
      />

      {agents.length === 0 ? (
        <EmptyState title="No agents for this project" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {agents.map((agent) => {
            const metrics = getAgentMetrics(agent.id)
            const overall = emptyCounts()
            for (const v of validations.filter((x) => x.agentId === agent.id)) {
              overall[v.verdict] += 1
            }
            const total = overall.PASS + overall.FAIL + overall.NO_EVIDENCE
            return (
              <Card key={agent.id}>
                <CardHeader>
                  <div>
                    <CardTitle>
                      <Link
                        to={`/projects/${projectId}/agents/${agent.id}`}
                        className="text-[var(--color-accent)] hover:underline"
                      >
                        {agentDisplayName(agent.name, workspace.name)}
                      </Link>
                    </CardTitle>
                    <div className="mt-1 text-xs text-[var(--color-muted)]">{agent.role}</div>
                  </div>
                  <AgentStatusBadge status={agent.status} />
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-xs text-[var(--color-fg-dim)]">{agent.description}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {agent.toolScope.map((t) => (
                      <span
                        key={t}
                        className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-fg-dim)]"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-2 text-center text-xs">
                    <div>
                      <div className="font-semibold text-[var(--color-pass)]">
                        {total ? formatPercent(overall.PASS / total) : '—'}
                      </div>
                      <div className="text-[var(--color-muted)]">PASS</div>
                    </div>
                    <div>
                      <div className="font-semibold text-[var(--color-fail)]">
                        {total ? formatPercent(overall.FAIL / total) : '—'}
                      </div>
                      <div className="text-[var(--color-muted)]">FAIL</div>
                    </div>
                    <div>
                      <div className="font-semibold text-[var(--color-none)]">
                        {total ? formatPercent(overall.NO_EVIDENCE / total) : '—'}
                      </div>
                      <div className="text-[var(--color-muted)]">NO EV</div>
                    </div>
                  </div>
                  <div className="text-[11px] text-[var(--color-muted)]">
                    Last active {formatRelative(agent.lastActiveAt)} · {metrics.totalJobs} jobs overall
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

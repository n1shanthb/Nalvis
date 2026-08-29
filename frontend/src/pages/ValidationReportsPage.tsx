import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { FilterChips, VerdictBadge } from '@/components/shared/status'
import { formatPercent, formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import type { ValidationVerdict } from '@/lib/demo/models'

export function ValidationReportsPage() {
  const { projectId = '' } = useParams()
  const { workspace, validations } = useProjectData(projectId)
  const agents = useDemoStore((s) => s.agents)
  const [verdict, setVerdict] = useState<ValidationVerdict | 'all'>('all')

  const filtered = useMemo(
    () => (verdict === 'all' ? validations : validations.filter((v) => v.verdict === verdict)),
    [validations, verdict],
  )

  const totals = useMemo(() => {
    const t = { PASS: 0, FAIL: 0, NO_EVIDENCE: 0, all: validations.length }
    for (const v of validations) t[v.verdict] += 1
    return t
  }, [validations])

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Validation`}
        description="Evidence-backed PASS / FAIL / NO_EVIDENCE for jobs in this project."
      />
      <MetricStrip
        items={[
          {
            label: 'PASS rate',
            value: formatPercent(totals.all ? totals.PASS / totals.all : 0),
            tone: 'pass',
          },
          { label: 'PASS', value: totals.PASS, tone: 'pass' },
          { label: 'FAIL', value: totals.FAIL, tone: 'fail' },
          { label: 'NO EVIDENCE', value: totals.NO_EVIDENCE, tone: 'warn' },
        ]}
      />

      <div className="mb-4">
        <FilterChips
          value={verdict}
          onChange={setVerdict}
          options={(['PASS', 'FAIL', 'NO_EVIDENCE'] as ValidationVerdict[]).map((v) => ({
            value: v,
            label: v.replace('_', ' '),
          }))}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No validation reports for this project" />
      ) : (
        <div className="space-y-4">
          {filtered.map((v) => (
            <Card key={v.id} id={v.id}>
              <CardHeader>
                <div>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    <span>{v.jobType}</span>
                    <VerdictBadge verdict={v.verdict} />
                  </CardTitle>
                  <CardDescription>
                    {v.id} ·{' '}
                    <Link
                      className="text-[var(--color-accent)] hover:underline"
                      to={`/projects/${projectId}/runs/${v.runId}`}
                    >
                      {v.runId}
                    </Link>{' '}
                    ·{' '}
                    <Link
                      className="text-[var(--color-accent)] hover:underline"
                      to={`/projects/${projectId}/agents/${v.agentId}`}
                    >
                      {agents.find((a) => a.id === v.agentId)?.name ?? v.agentId}
                    </Link>
                  </CardDescription>
                </div>
                <div className="text-xs text-[var(--color-muted)]">
                  conf {Math.round(v.confidence * 100)}% · {formatRelative(v.checkedAt)}
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p className="text-[var(--color-fg-dim)]">{v.message}</p>
                <div>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                    Reasoning
                  </div>
                  <p className="text-xs text-[var(--color-fg-dim)]">{v.reasoning}</p>
                </div>
                <div>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                    Checks
                  </div>
                  <ul className="space-y-1">
                    {v.checks.map((c) => (
                      <li
                        key={c.name}
                        className="flex flex-wrap items-center gap-2 rounded-md bg-[var(--color-bg)] px-2 py-1.5 text-xs"
                      >
                        <VerdictBadge verdict={c.passed ? 'PASS' : 'FAIL'} />
                        <span className="font-mono">{c.name}</span>
                        <span className="text-[var(--color-muted)]">{c.detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                    Evidence
                  </div>
                  {v.evidence ? (
                    <pre className="overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-[11px] text-[var(--color-fg-dim)]">
                      {JSON.stringify(v.evidence, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-xs text-[var(--color-muted)]">No evidence collected.</p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

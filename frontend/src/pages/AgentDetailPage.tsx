import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { AgentStatusBadge, JobStatusBadge, VerdictBadge } from '@/components/shared/status'
import { formatPercent, formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import type { GuardrailMode } from '@/lib/demo/models'

const MODE_OPTIONS: { value: GuardrailMode; label: string }[] = [
  { value: 'allow', label: 'Allow' },
  { value: 'hil', label: 'Require HIL' },
  { value: 'deny', label: 'Deny' },
  { value: 'auto', label: 'Auto-run' },
]

function modeBadge(mode: GuardrailMode) {
  if (mode === 'allow') return 'pass' as const
  if (mode === 'hil') return 'warn' as const
  if (mode === 'deny') return 'fail' as const
  return 'accent' as const
}

export function AgentDetailPage() {
  const { projectId = '', agentId = '' } = useParams()
  const { workspace, jobs: projectJobs, validations: projectValidations } =
    useProjectData(projectId)
  const agents = useDemoStore((s) => s.agents)
  const agent = agents.find((a) => a.id === agentId)
  const docs = useDemoStore((s) => s.contextDocuments)
  const addAgentGuardrail = useDemoStore((s) => s.addAgentGuardrail)
  const updateAgentGuardrail = useDemoStore((s) => s.updateAgentGuardrail)
  const removeAgentGuardrail = useDemoStore((s) => s.removeAgentGuardrail)

  const jobs = useMemo(
    () => projectJobs.filter((j) => j.agentId === agentId),
    [projectJobs, agentId],
  )
  const validations = useMemo(
    () => projectValidations.filter((v) => v.agentId === agentId),
    [projectValidations, agentId],
  )

  const [tool, setTool] = useState('')
  const [mode, setMode] = useState<GuardrailMode>('hil')
  const [label, setLabel] = useState('')
  const [rationale, setRationale] = useState('')
  const [busy, setBusy] = useState(false)

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  if (!agent || !agent.workspaceIds.includes(projectId)) {
    return (
      <EmptyState
        title="Agent not found in this project"
        description={`No agent ${agentId} for ${workspace.name}`}
      />
    )
  }

  const counts = { PASS: 0, FAIL: 0, NO_EVIDENCE: 0 }
  for (const v of validations) counts[v.verdict] += 1
  const total = counts.PASS + counts.FAIL + counts.NO_EVIDENCE
  const score = total ? counts.PASS / total : null

  const toolChoices = Array.from(
    new Set([
      ...agent.toolScope,
      ...agent.guardrails.map((g) => g.tool).filter((t) => t !== '*'),
      'github.merge_pr',
      'jira.create_issue',
      'gmail.send',
      'calendar.create_event',
    ]),
  )

  async function onAddGuardrail() {
    if (!tool.trim()) return
    setBusy(true)
    try {
      await addAgentGuardrail(agentId, {
        tool: tool.trim(),
        mode,
        label: label.trim() || undefined,
        rationale: rationale.trim() || undefined,
      })
      setLabel('')
      setRationale('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={agent.name}
        description={`${agent.role} · ${workspace.name}`}
        actions={<AgentStatusBadge status={agent.status} />}
      />
      <p className="mb-4 max-w-3xl text-sm text-[var(--color-fg-dim)]">{agent.description}</p>

      <MetricStrip
        items={[
          { label: 'Jobs in project', value: jobs.length },
          {
            label: 'Validation score',
            value: score == null ? '—' : formatPercent(score),
            tone: score == null ? 'default' : score >= 0.7 ? 'pass' : score >= 0.4 ? 'warn' : 'fail',
            hint: total ? `${counts.PASS} PASS / ${total} checks` : 'No validations yet',
          },
          { label: 'FAIL', value: counts.FAIL, tone: 'fail' },
          { label: 'NO EVIDENCE', value: counts.NO_EVIDENCE, tone: 'warn' },
        ]}
      />

      <div className="mb-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Mission</CardTitle>
            <CardDescription>Why this agent exists as an executor (not a chatbot).</CardDescription>
          </CardHeader>
          <CardContent className="text-sm leading-relaxed text-[var(--color-fg-dim)]">
            {agent.mission}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Origin evidence</CardTitle>
            <CardDescription>
              Synthesized from ingested context ·{' '}
              <span className="font-mono">{agent.origin.contextDocumentName}</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-[var(--color-fg-dim)]">{agent.origin.rationale}</p>
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                KG signals
              </div>
              <ul className="space-y-1 text-xs text-[var(--color-fg-dim)]">
                {agent.origin.signals.map((s) => (
                  <li key={s} className="rounded-md bg-[var(--color-surface-2)] px-2 py-1.5">
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                KG paths
              </div>
              <ul className="space-y-0.5 font-mono text-[11px] text-[var(--color-muted)]">
                {agent.origin.kgPaths.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
            <div className="text-[11px] text-[var(--color-muted)]">
              From doc {agent.origin.contextDocumentId}
              {docs[0] ? ` · latest ingest ${docs[0].name}` : ''} ·{' '}
              {formatRelative(agent.origin.synthesizedAt)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Full specs</CardTitle>
          <CardDescription>Runtime contract and least-privilege tool boundary.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm md:grid-cols-2 lg:grid-cols-3">
          <Spec label="Runtime" value={agent.specs.runtime} />
          <Spec label="Model hint" value={agent.specs.modelHint} />
          <Spec label="Max concurrency" value={String(agent.specs.maxConcurrency)} />
          <Spec label="Timeout" value={`${agent.specs.timeoutSec}s`} />
          <Spec label="Input schema" value={agent.specs.inputSchema.join(', ')} mono />
          <Spec label="Output schema" value={agent.specs.outputSchema.join(', ')} mono />
          <div className="md:col-span-2 lg:col-span-3">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              Tool scope
            </div>
            <div className="flex flex-wrap gap-1.5">
              {agent.toolScope.map((t) => (
                <span
                  key={t}
                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 font-mono text-[11px]"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div className="md:col-span-2 lg:col-span-3">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              Memory keys
            </div>
            <ul className="font-mono text-[11px] text-[var(--color-muted)]">
              {agent.specs.memoryKeys.map((k) => (
                <li key={k}>{k}</li>
              ))}
            </ul>
          </div>
          <p className="md:col-span-2 lg:col-span-3 text-xs text-[var(--color-fg-dim)]">
            {agent.specs.leastPrivilegeNote}
          </p>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <div>
            <CardTitle>Guardrails</CardTitle>
            <CardDescription>
              Per-agent rules synthesized from KG + tools (varied by agent). Add operator rules below.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {agent.guardrails.map((g) => (
              <div
                key={g.id}
                className="flex flex-col gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sm">{g.label}</span>
                    <Badge variant={modeBadge(g.mode)}>{g.mode}</Badge>
                    <Badge variant={g.source === 'user' ? 'accent' : 'default'}>{g.source}</Badge>
                  </div>
                  <div className="font-mono text-[11px] text-[var(--color-muted)]">{g.tool}</div>
                  <p className="text-xs text-[var(--color-fg-dim)]">{g.rationale}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <label className="sr-only" htmlFor={`mode-${g.id}`}>
                    Mode for {g.label}
                  </label>
                  <select
                    id={`mode-${g.id}`}
                    className="h-8 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs"
                    value={g.mode}
                    onChange={(e) =>
                      void updateAgentGuardrail(agentId, g.id, {
                        mode: e.target.value as GuardrailMode,
                      })
                    }
                  >
                    {MODE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => void removeAgentGuardrail(agentId, g.id)}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-2)]/60 p-4">
            <div className="mb-3 text-sm font-medium">Add guardrail</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wider text-[var(--color-muted)]" htmlFor="new-tool">
                  Tool
                </label>
                <select
                  id="new-tool"
                  className="h-9 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm"
                  value={tool}
                  onChange={(e) => setTool(e.target.value)}
                >
                  <option value="">Select tool…</option>
                  {toolChoices.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wider text-[var(--color-muted)]" htmlFor="new-mode">
                  Mode
                </label>
                <select
                  id="new-mode"
                  className="h-9 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as GuardrailMode)}
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wider text-[var(--color-muted)]" htmlFor="new-label">
                  Label (optional)
                </label>
                <Input
                  id="new-label"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="e.g. Block merge on main"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wider text-[var(--color-muted)]" htmlFor="new-rationale">
                  Rationale (optional)
                </label>
                <Input
                  id="new-rationale"
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="Why this rule exists"
                />
              </div>
            </div>
            <div className="mt-3">
              <Button disabled={busy || !tool} onClick={() => void onAddGuardrail()}>
                Add guardrail
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Run history in {workspace.name}</CardTitle>
          <CardDescription>Last active {formatRelative(agent.lastActiveAt)}</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {jobs.length === 0 ? (
            <p className="text-sm text-[var(--color-muted)]">No jobs in this project yet.</p>
          ) : (
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                <tr className="border-b border-[var(--color-border)]">
                  <th className="pb-2 font-medium">Job</th>
                  <th className="pb-2 font-medium">Run</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Validation</th>
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
                          {job.jobType}
                        </div>
                      </td>
                      <td className="py-3">
                        <Link
                          className="text-[var(--color-accent)] hover:underline"
                          to={`/projects/${projectId}/runs/${job.runId}`}
                        >
                          {job.runId}
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
                          '—'
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function Spec({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <div className={mono ? 'font-mono text-xs text-[var(--color-fg-dim)]' : 'text-[var(--color-fg)]'}>
        {value}
      </div>
    </div>
  )
}

import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { PageHeader, EmptyState } from '@/components/shared/page'
import { AgentStatusBadge } from '@/components/shared/status'
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

export function PoliciesPage() {
  const { projectId = '' } = useParams()
  const { workspace, policy, agents } = useProjectData(projectId)
  const updatePolicy = useDemoStore((s) => s.updatePolicy)
  const updateAgentGuardrail = useDemoStore((s) => s.updateAgentGuardrail)

  if (!workspace || !policy) {
    return <EmptyState title="No policies for this project" />
  }

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Policies`}
        description="Workspace action toggles plus each agent’s guardrail policies for this project."
      />

      <Card className="mb-4">
        <CardHeader>
          <div>
            <CardTitle>Workspace action settings</CardTitle>
            <CardDescription>
              Scoped to {workspace.name} · {workspace.scope.repos.join(', ') || 'no repos'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              <tr className="border-b border-[var(--color-border)]">
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium">Allowed</th>
                <th className="pb-2 font-medium">HIL required</th>
                <th className="pb-2 font-medium">Auto-merge</th>
              </tr>
            </thead>
            <tbody>
              {policy.actions.map((action) => (
                <tr key={action.action} className="border-b border-[var(--color-border)]/60">
                  <td className="py-3">
                    <div className="font-medium">{action.label}</div>
                    <div className="font-mono text-[11px] text-[var(--color-muted)]">
                      {action.action}
                    </div>
                  </td>
                  <td className="py-3">
                    <Switch
                      label={`${action.action} allowed`}
                      checked={action.allowed}
                      onCheckedChange={(v) =>
                        void updatePolicy(projectId, action.action, { allowed: v })
                      }
                    />
                  </td>
                  <td className="py-3">
                    <Switch
                      label={`${action.action} HIL`}
                      checked={action.hilRequired}
                      onCheckedChange={(v) =>
                        void updatePolicy(projectId, action.action, { hilRequired: v })
                      }
                    />
                  </td>
                  <td className="py-3">
                    <Switch
                      label={`${action.action} auto-merge`}
                      checked={action.autoMerge}
                      onCheckedChange={(v) =>
                        void updatePolicy(projectId, action.action, { autoMerge: v })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-fg)]">Agent guardrail policies</h2>
          <p className="mt-0.5 text-xs text-[var(--color-muted)]">
            {agents.length} agents in {workspace.name} — synthesized + operator rules.
          </p>
        </div>
        <Link
          to={`/projects/${projectId}/agents`}
          className="text-xs text-[var(--color-accent)] hover:underline"
        >
          Open agents →
        </Link>
      </div>

      {agents.length === 0 ? (
        <EmptyState title="No agents in this workspace" />
      ) : (
        <div className="space-y-4">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <CardHeader>
                <div>
                  <CardTitle>
                    <Link
                      to={`/projects/${projectId}/agents/${agent.id}`}
                      className="text-[var(--color-accent)] hover:underline"
                    >
                      {agent.name}
                    </Link>
                  </CardTitle>
                  <CardDescription>
                    {agent.role} · {agent.guardrails.length} guardrails ·{' '}
                    <span className="font-mono text-[10px]">{agent.id}</span>
                  </CardDescription>
                </div>
                <AgentStatusBadge status={agent.status} />
              </CardHeader>
              <CardContent className="overflow-x-auto">
                {agent.guardrails.length === 0 ? (
                  <p className="text-sm text-[var(--color-muted)]">No guardrails on this agent.</p>
                ) : (
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                      <tr className="border-b border-[var(--color-border)]">
                        <th className="pb-2 font-medium">Rule</th>
                        <th className="pb-2 font-medium">Tool</th>
                        <th className="pb-2 font-medium">Source</th>
                        <th className="pb-2 font-medium">Mode</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agent.guardrails.map((g) => (
                        <tr key={g.id} className="border-b border-[var(--color-border)]/60 align-top">
                          <td className="py-3 pr-3">
                            <div className="font-medium">{g.label}</div>
                            <div className="mt-0.5 text-xs text-[var(--color-muted)]">{g.rationale}</div>
                          </td>
                          <td className="py-3 pr-3 font-mono text-[11px] text-[var(--color-fg-dim)]">
                            {g.tool}
                          </td>
                          <td className="py-3 pr-3">
                            <Badge variant={g.source === 'user' ? 'accent' : 'default'}>
                              {g.source}
                            </Badge>
                          </td>
                          <td className="py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={modeBadge(g.mode)}>{g.mode}</Badge>
                              <label className="sr-only" htmlFor={`policy-mode-${g.id}`}>
                                Mode for {g.label}
                              </label>
                              <select
                                id={`policy-mode-${g.id}`}
                                className="h-8 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs"
                                value={g.mode}
                                onChange={(e) =>
                                  void updateAgentGuardrail(agent.id, g.id, {
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
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

import { Link, Navigate, useParams } from 'react-router-dom'
import {
  Bot,
  CheckSquare,
  ScrollText,
  Shield,
  Workflow,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import { formatPercent } from '@/lib/utils'

export function ProjectOverviewPage() {
  const { projectId = '' } = useParams()
  const { workspace, runs, pendingApprovals, validations, agents, policy } =
    useProjectData(projectId)

  if (!workspace) {
    return <EmptyState title="Project not found" description={`No project ${projectId}`} />
  }

  const pass = validations.filter((v) => v.verdict === 'PASS').length
  const total = validations.length

  const sections = [
    {
      to: `/projects/${projectId}/runs`,
      title: 'Runs',
      desc: 'Orchestration jobs for this product',
      icon: Workflow,
      stat: String(runs.length),
    },
    {
      to: `/projects/${projectId}/approvals`,
      title: 'Approvals',
      desc: 'HIL inbox scoped to this project',
      icon: CheckSquare,
      stat: String(pendingApprovals.length),
    },
    {
      to: `/projects/${projectId}/policies`,
      title: 'Policies',
      desc: 'Action allow / HIL / auto-merge',
      icon: Shield,
      stat: String(policy?.actions.length ?? 0),
    },
    {
      to: `/projects/${projectId}/validation`,
      title: 'Validation',
      desc: 'PASS / FAIL / NO_EVIDENCE reports',
      icon: ScrollText,
      stat: String(validations.length),
    },
    {
      to: `/projects/${projectId}/agents`,
      title: 'Agents',
      desc: 'Executors assigned to this project',
      icon: Bot,
      stat: String(agents.length),
    },
  ]

  return (
    <div>
      <PageHeader title={workspace.name} description={workspace.description} />
      <MetricStrip
        items={[
          { label: 'Runs', value: runs.length, tone: 'accent' },
          {
            label: 'Pending approvals',
            value: pendingApprovals.length,
            tone: pendingApprovals.length ? 'warn' : 'pass',
          },
          {
            label: 'PASS rate',
            value: total ? formatPercent(pass / total) : '—',
            tone: 'pass',
          },
          { label: 'Agents', value: agents.length },
        ]}
      />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Project scope</CardTitle>
          <CardDescription>Derived from company context for this product workspace.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-xs text-[var(--color-fg-dim)] sm:grid-cols-2 lg:grid-cols-4">
          <ScopeBlock label="Repos" items={workspace.scope.repos} />
          <ScopeBlock label="Jira" items={workspace.scope.jiraKeys} />
          <ScopeBlock label="Calendars" items={workspace.scope.calendars} />
          <ScopeBlock label="Email groups" items={workspace.scope.emailGroups} />
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {sections.map((s) => {
          const Icon = s.icon
          return (
            <Link key={s.to} to={s.to}>
              <Card className="h-full transition-colors hover:border-[var(--color-accent)]/40">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-[var(--color-accent)]" aria-hidden />
                    <CardTitle>{s.title}</CardTitle>
                  </div>
                  <CardDescription>{s.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-semibold tabular-nums">{s.stat}</div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

function ScopeBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      {items.length === 0 ? (
        <div>—</div>
      ) : (
        <ul className="space-y-0.5 font-mono">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ProjectsIndexPage() {
  const workspaces = useDemoStore((s) => s.workspaces)
  const approvals = useDemoStore((s) => s.approvals)
  const runs = useDemoStore((s) => s.runs)

  if (workspaces.length === 1) {
    return <Navigate to={`/projects/${workspaces[0]!.id}`} replace />
  }

  return (
    <div>
      <PageHeader
        title="Projects"
        description="Each product project has its own runs, approvals, policies, validation, and agents."
      />
      {workspaces.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Workspaces appear here after real company context is ingested and the control plane creates product projects. Empty is expected until then."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workspaces.map((ws) => {
            const pending = approvals.filter(
              (a) => a.workspaceId === ws.id && a.decision === 'pending',
            ).length
            const runCount = runs.filter((r) => r.workspaceIds.includes(ws.id)).length
            return (
              <Link key={ws.id} to={`/projects/${ws.id}`}>
                <Card className="h-full transition-colors hover:border-[var(--color-accent)]/40">
                  <CardHeader>
                    <CardTitle>{ws.name}</CardTitle>
                    <CardDescription>{ws.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="text-xs text-[var(--color-muted)]">
                    {runCount} runs · {pending} pending approvals · {ws.scope.repos.length} repos
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

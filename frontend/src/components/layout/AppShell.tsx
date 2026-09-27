import { NavLink, Outlet, useParams } from 'react-router-dom'
import {
  Activity,
  Bot,
  Boxes,
  CheckSquare,
  FileSearch,
  Gauge,
  LayoutDashboard,
  Plug,
  ScrollText,
  Shield,
  Workflow,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { getAdapterMode } from '@/lib/api'
import { useDemoStore } from '@/lib/store'

const globalNav = [
  { to: '/ops', label: 'Ops console', icon: LayoutDashboard },
  { to: '/context', label: 'Context Studio', icon: FileSearch },
  { to: '/projects', label: 'All projects', icon: Boxes },
  { to: '/integrations', label: 'Integrations', icon: Plug },
]

const projectSections = [
  { segment: '', label: 'Overview', icon: Gauge, end: true },
  { segment: 'runs', label: 'Runs', icon: Workflow, end: false },
  { segment: 'approvals', label: 'Approvals', icon: CheckSquare, end: false },
  { segment: 'policies', label: 'Policies', icon: Shield, end: false },
  { segment: 'validation', label: 'Validation', icon: ScrollText, end: false },
  { segment: 'agents', label: 'Agents', icon: Bot, end: false },
]

export function AppShell() {
  const companyName = useDemoStore((s) => s.companyName)
  const workspaces = useDemoStore((s) => s.workspaces)
  const approvals = useDemoStore((s) => s.approvals)
  const { projectId } = useParams()
  const activeProject = workspaces.find((w) => w.id === projectId)

  function pendingFor(wsId: string) {
    return approvals.filter((a) => a.workspaceId === wsId && a.decision === 'pending').length
  }

  return (
    <div className="flex min-h-full">
      <aside
        className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur"
        aria-label="Primary"
      >
        <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
            <Gauge className="h-4 w-4" aria-hidden />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">AgentSuite</div>
            <div className="text-[11px] text-[var(--color-muted)]">Ops console</div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto p-2" aria-label="Console sections">
          <div className="mb-3 space-y-0.5">
            {globalNav.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/ops' || item.to === '/projects'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
                      isActive
                        ? 'bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
                        : 'text-[var(--color-fg-dim)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)]',
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden />
                  {item.label}
                </NavLink>
              )
            })}
          </div>

          <div className="mb-1 px-3 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-muted)]">
            Projects
          </div>
          <div className="space-y-1">
            {workspaces.map((ws) => {
              const pending = pendingFor(ws.id)
              const isOpen = projectId === ws.id
              return (
                <div key={ws.id}>
                  <NavLink
                    to={`/projects/${ws.id}`}
                    end
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        isActive || isOpen
                          ? 'bg-[var(--color-surface-2)] text-[var(--color-fg)]'
                          : 'text-[var(--color-fg-dim)] hover:bg-[var(--color-surface-2)]/70 hover:text-[var(--color-fg)]',
                      )
                    }
                  >
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-accent)]/15 text-[10px] font-bold text-[var(--color-accent)]" aria-hidden>
                      {ws.name.slice(0, 1)}
                    </span>
                    <span className="flex-1 truncate">{ws.name}</span>
                    {pending > 0 ? (
                      <span
                        className="rounded-full bg-[var(--color-warn)]/20 px-1.5 text-[10px] font-semibold text-[var(--color-warn)]"
                        aria-hidden
                      >
                        {pending}
                      </span>
                    ) : null}
                  </NavLink>

                  {isOpen ? (
                    <div className="ml-3 mt-0.5 space-y-0.5 border-l border-[var(--color-border)] pl-2">
                      {projectSections.map((section) => {
                        const Icon = section.icon
                        const to =
                          section.segment === ''
                            ? `/projects/${ws.id}`
                            : `/projects/${ws.id}/${section.segment}`
                        return (
                          <NavLink
                            key={section.label}
                            to={to}
                            end={section.end}
                            className={({ isActive }) =>
                              cn(
                                'flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs transition-colors',
                                isActive
                                  ? 'bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
                                  : 'text-[var(--color-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)]',
                              )
                            }
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                            <span className="flex-1">{section.label}</span>
                            {section.segment === 'approvals' && pending > 0 ? (
                              <span className="text-[10px] text-[var(--color-warn)]" aria-hidden>
                                {pending}
                              </span>
                            ) : null}
                          </NavLink>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </nav>

        <div className="border-t border-[var(--color-border)] p-4 text-[11px] text-[var(--color-muted)]">
          <div className="flex items-center gap-1.5">
            <Activity className="h-3 w-3" aria-hidden />
            {getAdapterMode() === 'http' ? 'Live API' : 'Local store'}
          </div>
          <div className="mt-1 truncate">{companyName || 'No company loaded'}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 px-6 backdrop-blur">
          <div className="text-xs text-[var(--color-muted)]">
            {activeProject ? (
              <>
                Project · <span className="text-[var(--color-fg-dim)]">{activeProject.name}</span>
                <span className="mx-2 text-[var(--color-border-strong)]">·</span>
                {activeProject.scope.repos.length} repos · {activeProject.scope.jiraKeys.join(', ') || 'no jira'}
              </>
            ) : (
              'Single-tenant · multi-product · evidence-backed validation'
            )}
          </div>
          <div className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-[11px] text-[var(--color-fg-dim)]">
            No synthetic data
          </div>
        </header>
        <main className="flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

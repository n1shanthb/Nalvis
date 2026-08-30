import { NavLink, Outlet, useParams } from 'react-router-dom'
import { Bot } from 'lucide-react'
import { cn, agentDisplayName } from '@/lib/utils'
import { useProjectData } from '@/lib/useProjectData'
import { AgentStatusBadge } from '@/components/shared/status'
import { EmptyState } from '@/components/shared/page'

export function AgentsLayout() {
  const { projectId = '', agentId } = useParams()
  const { workspace, agents } = useProjectData(projectId)

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  return (
    <div className="-mx-6 -my-6 flex min-h-[calc(100vh-3.5rem)]">
      <aside
        className="sticky top-14 flex h-[calc(100vh-3.5rem)] w-56 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]"
        aria-label="Project agents"
      >
        <div className="border-b border-[var(--color-border)] px-3 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]">
            <Bot className="h-3.5 w-3.5" aria-hidden />
            Agents
          </div>
          <div className="mt-0.5 truncate text-[11px] text-[var(--color-fg-dim)]">
            {workspace.name} · {agents.length}
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Agent list">
          <NavLink
            to={`/projects/${projectId}/agents`}
            end
            className={({ isActive }) =>
              cn(
                'flex items-center rounded-lg px-2.5 py-2 text-xs font-medium transition-colors',
                isActive && !agentId
                  ? 'bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
                  : 'text-[var(--color-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)]',
              )
            }
          >
            All agents
          </NavLink>

          <div className="my-2 border-t border-[var(--color-border)]" />

          {agents.map((a) => (
            <NavLink
              key={a.id}
              to={`/projects/${projectId}/agents/${a.id}`}
              className={({ isActive }) =>
                cn(
                  'block rounded-lg px-2.5 py-2 transition-colors',
                  isActive
                    ? 'bg-[var(--color-accent)]/15 ring-1 ring-[var(--color-accent)]/25'
                    : 'hover:bg-[var(--color-surface-2)]',
                )
              }
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div
                    className={cn(
                      'truncate text-sm font-medium',
                      a.id === agentId ? 'text-[var(--color-accent)]' : 'text-[var(--color-fg)]',
                    )}
                  >
                    {agentDisplayName(a.name, workspace.name)}
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-[var(--color-muted)]">
                    {a.role}
                  </div>
                </div>
                <AgentStatusBadge status={a.status} />
              </div>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1 overflow-y-auto px-6 py-6">
        <Outlet />
      </div>
    </div>
  )
}

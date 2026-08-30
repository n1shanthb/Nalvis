import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { LoadingState } from '@/components/shared/page'
import { useDemoStore } from '@/lib/store'
import { ContextStudioPage } from '@/pages/ContextStudioPage'
import { ProjectsIndexPage, ProjectOverviewPage } from '@/pages/ProjectPages'
import { RunsPage } from '@/pages/RunsPage'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { ApprovalsPage } from '@/pages/ApprovalsPage'
import { PoliciesPage } from '@/pages/PoliciesPage'
import { IntegrationsPage } from '@/pages/IntegrationsPage'
import { ValidationReportsPage } from '@/pages/ValidationReportsPage'
import { AgentsPage } from '@/pages/AgentsPage'
import { AgentDetailPage } from '@/pages/AgentDetailPage'
import { AgentsLayout } from '@/components/layout/AgentsLayout'

export default function App() {
  const hydrate = useDemoStore((s) => s.hydrate)
  const hydrated = useDemoStore((s) => s.hydrated)

  useEffect(() => {
    void hydrate()
  }, [hydrate])

  // HIL / runs arrive via webhooks while the SPA stays open — refresh on focus
  // so Approvals badges and lists match the control plane.
  useEffect(() => {
    function onFocus() {
      void hydrate()
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [hydrate])

  if (!hydrated) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <LoadingState />
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/projects" replace />} />
          <Route path="context" element={<ContextStudioPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="projects" element={<ProjectsIndexPage />} />
          <Route path="projects/:projectId" element={<ProjectOverviewPage />} />
          <Route path="projects/:projectId/runs" element={<RunsPage />} />
          <Route path="projects/:projectId/runs/:runId" element={<RunDetailPage />} />
          <Route path="projects/:projectId/approvals" element={<ApprovalsPage />} />
          <Route path="projects/:projectId/policies" element={<PoliciesPage />} />
          <Route path="projects/:projectId/validation" element={<ValidationReportsPage />} />
          <Route path="projects/:projectId/agents" element={<AgentsLayout />}>
            <Route index element={<AgentsPage />} />
            <Route path=":agentId" element={<AgentDetailPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

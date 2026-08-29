import { useMemo } from 'react'
import { useDemoStore } from '@/lib/store'

/** Stable project-scoped slices — never filter inside Zustand selectors (new array → infinite rerenders). */
export function useProjectData(projectId: string) {
  const workspace = useDemoStore((s) => s.workspaces.find((w) => w.id === projectId))
  const runsAll = useDemoStore((s) => s.runs)
  const jobsAll = useDemoStore((s) => s.jobs)
  const approvalsAll = useDemoStore((s) => s.approvals)
  const validationsAll = useDemoStore((s) => s.validations)
  const agentsAll = useDemoStore((s) => s.agents)
  const policiesAll = useDemoStore((s) => s.policies)
  const timelineAll = useDemoStore((s) => s.timeline)

  const runs = useMemo(
    () => runsAll.filter((r) => r.workspaceIds.includes(projectId)),
    [runsAll, projectId],
  )
  const jobs = useMemo(
    () => jobsAll.filter((j) => j.workspaceId === projectId),
    [jobsAll, projectId],
  )
  const approvals = useMemo(
    () => approvalsAll.filter((a) => a.workspaceId === projectId),
    [approvalsAll, projectId],
  )
  const pendingApprovals = useMemo(
    () => approvals.filter((a) => a.decision === 'pending'),
    [approvals],
  )
  const validations = useMemo(
    () => validationsAll.filter((v) => v.workspaceId === projectId),
    [validationsAll, projectId],
  )
  const agents = useMemo(
    () => agentsAll.filter((a) => a.workspaceIds.includes(projectId)),
    [agentsAll, projectId],
  )
  const policy = useMemo(
    () => policiesAll.find((p) => p.workspaceId === projectId),
    [policiesAll, projectId],
  )
  const timeline = useMemo(
    () => timelineAll.filter((t) => runs.some((r) => r.id === t.runId)),
    [timelineAll, runs],
  )

  return {
    workspace,
    runs,
    jobs,
    approvals,
    pendingApprovals,
    validations,
    agents,
    policy,
    timeline,
  }
}

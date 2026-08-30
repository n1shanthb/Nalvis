import { create } from 'zustand'
import { getAdapter } from '@/lib/api'
import { computeAgentMetrics, type NewGuardrailInput } from '@/lib/api/types'
import type {
  Agent,
  AgentGuardrail,
  AgentMetrics,
  ApprovalDecision,
  ApprovalItem,
  ContextDocument,
  DemoState,
  IntegrationHealth,
  Job,
  Run,
  TimelineEvent,
  ValidationOutcome,
  Workspace,
  WorkspacePolicy,
} from '@/lib/demo/models'

interface DemoStore extends DemoState {
  hydrated: boolean
  hydrate: () => Promise<void>
  clearAllData: () => Promise<void>
  ingestContext: (raw: string, source: 'paste' | 'upload') => Promise<ContextDocument>
  startRun: (objectives?: string[], workspaceIds?: string[]) => Promise<void>
  decideApproval: (
    approvalId: string,
    decision: Exclude<ApprovalDecision, 'pending'>,
    editedPayload?: string,
  ) => Promise<void>
  updatePolicy: (
    workspaceId: string,
    action: string,
    patch: Partial<Pick<WorkspacePolicy['actions'][number], 'allowed' | 'hilRequired' | 'autoMerge'>>,
  ) => Promise<void>
  addAgentGuardrail: (agentId: string, input: NewGuardrailInput) => Promise<void>
  updateAgentGuardrail: (
    agentId: string,
    guardrailId: string,
    patch: Partial<Pick<AgentGuardrail, 'mode' | 'label' | 'rationale' | 'tool'>>,
  ) => Promise<void>
  removeAgentGuardrail: (agentId: string, guardrailId: string) => Promise<void>
  getJobsForRun: (runId: string) => Job[]
  getTimelineForRun: (runId: string) => TimelineEvent[]
  getAgentMetrics: (agentId: string) => AgentMetrics
  getWorkspace: (id: string) => Workspace | undefined
  getAgent: (id: string) => Agent | undefined
  getRun: (id: string) => Run | undefined
  pendingApprovals: () => ApprovalItem[]
}

async function snapshot(): Promise<DemoState> {
  return getAdapter().getState()
}

export const useDemoStore = create<DemoStore>((set, get) => ({
  companyName: '',
  contextDocuments: [],
  workspaces: [],
  runs: [],
  jobs: [],
  timeline: [],
  approvals: [],
  policies: [],
  integrations: [],
  validations: [],
  agents: [],
  hydrated: false,

  hydrate: async () => {
    const state = await snapshot()
    set({ ...state, hydrated: true })
  },

  clearAllData: async () => {
    const state = await getAdapter().clearAllData()
    set({ ...state, hydrated: true })
  },

  ingestContext: async (raw, source) => {
    const doc = await getAdapter().ingestContext(raw, source)
    const state = await snapshot()
    set({ ...state })
    return doc
  },

  startRun: async (objectives, workspaceIds) => {
    const wsIds = workspaceIds?.length ? workspaceIds : get().workspaces.map((w) => w.id)
    if (wsIds.length === 0) throw new Error('No workspaces — ingest context first')
    // Objective-only: Director + Routing Auditor select specialists (LLM when key set).
    // Do not hardcode a demo plan of github+gmail+calendar.
    await getAdapter().startRun({
      title: objectives?.[0] || 'Company run',
      objectives: objectives ?? ['Execute work implied by workspace inventory and live agents'],
      workspaceIds: wsIds,
      plan: [],
    })
    set({ ...(await snapshot()) })
  },

  decideApproval: async (approvalId, decision, editedPayload) => {
    await getAdapter().decideApproval(approvalId, decision, editedPayload)
    const state = await snapshot()
    set({ ...state })
  },

  updatePolicy: async (workspaceId, action, patch) => {
    await getAdapter().updatePolicy(workspaceId, action, patch)
    const state = await snapshot()
    set({ ...state })
  },

  addAgentGuardrail: async (agentId, input) => {
    await getAdapter().addAgentGuardrail(agentId, input)
    set({ ...(await snapshot()) })
  },

  updateAgentGuardrail: async (agentId, guardrailId, patch) => {
    await getAdapter().updateAgentGuardrail(agentId, guardrailId, patch)
    set({ ...(await snapshot()) })
  },

  removeAgentGuardrail: async (agentId, guardrailId) => {
    await getAdapter().removeAgentGuardrail(agentId, guardrailId)
    set({ ...(await snapshot()) })
  },

  getJobsForRun: (runId) => get().jobs.filter((j) => j.runId === runId),
  getTimelineForRun: (runId) =>
    get()
      .timeline.filter((t) => t.runId === runId)
      .sort((a, b) => a.at.localeCompare(b.at)),
  getAgentMetrics: (agentId) =>
    computeAgentMetrics(agentId, get().validations, get().jobs),
  getWorkspace: (id) => get().workspaces.find((w) => w.id === id),
  getAgent: (id) => get().agents.find((a) => a.id === id),
  getRun: (id) => get().runs.find((r) => r.id === id),
  pendingApprovals: () => get().approvals.filter((a) => a.decision === 'pending'),
}))

export type {
  Agent,
  ApprovalItem,
  IntegrationHealth,
  Job,
  Run,
  ValidationOutcome,
  Workspace,
  WorkspacePolicy,
}

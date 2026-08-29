import type {
  Agent,
  AgentGuardrail,
  AgentMetrics,
  ApprovalDecision,
  ApprovalItem,
  ContextDocument,
  DemoState,
  GuardrailMode,
  IntegrationHealth,
  Job,
  Run,
  TimelineEvent,
  ValidationOutcome,
  ValidationVerdict,
  Workspace,
  WorkspacePolicy,
} from '@/lib/demo/models'

export type NewGuardrailInput = {
  tool: string
  mode: GuardrailMode
  label?: string
  rationale?: string
}

export type StartRunInput = {
  title?: string
  objectives?: string[]
  workspaceIds: string[]
  plan?: Array<Record<string, unknown>>
  signal?: Record<string, unknown>
}

export interface ApiAdapter {
  getState(): Promise<DemoState>
  clearAllData(): Promise<DemoState>
  ingestContext(raw: string, source: 'paste' | 'upload'): Promise<ContextDocument>
  listWorkspaces(): Promise<Workspace[]>
  listRuns(): Promise<Run[]>
  getRun(runId: string): Promise<Run | undefined>
  startRun(input: StartRunInput): Promise<Run>
  listJobs(runId?: string): Promise<Job[]>
  listTimeline(runId: string): Promise<TimelineEvent[]>
  listApprovals(decision?: ApprovalDecision): Promise<ApprovalItem[]>
  decideApproval(
    approvalId: string,
    decision: Exclude<ApprovalDecision, 'pending'>,
    editedPayload?: string,
  ): Promise<ApprovalItem | undefined>
  listPolicies(): Promise<WorkspacePolicy[]>
  updatePolicy(
    workspaceId: string,
    action: string,
    patch: Partial<Pick<WorkspacePolicy['actions'][number], 'allowed' | 'hilRequired' | 'autoMerge'>>,
  ): Promise<WorkspacePolicy | undefined>
  listIntegrations(): Promise<IntegrationHealth[]>
  listValidations(): Promise<ValidationOutcome[]>
  listAgents(): Promise<Agent[]>
  getAgent(agentId: string): Promise<Agent | undefined>
  getAgentMetrics(agentId: string): Promise<AgentMetrics | undefined>
  addAgentGuardrail(agentId: string, input: NewGuardrailInput): Promise<AgentGuardrail | undefined>
  updateAgentGuardrail(
    agentId: string,
    guardrailId: string,
    patch: Partial<Pick<AgentGuardrail, 'mode' | 'label' | 'rationale' | 'tool'>>,
  ): Promise<AgentGuardrail | undefined>
  removeAgentGuardrail(agentId: string, guardrailId: string): Promise<boolean>
}

export function emptyVerdictCounts(): Record<ValidationVerdict, number> {
  return { PASS: 0, FAIL: 0, NO_EVIDENCE: 0 }
}

export function computeAgentMetrics(
  agentId: string,
  validations: ValidationOutcome[],
  jobs: Job[],
): AgentMetrics {
  const agentValidations = validations.filter((v) => v.agentId === agentId)
  const overall = emptyVerdictCounts()
  const byJobType: AgentMetrics['byJobType'] = {}
  const byWorkspace: AgentMetrics['byWorkspace'] = {}

  for (const v of agentValidations) {
    overall[v.verdict] += 1
    byJobType[v.jobType] ??= emptyVerdictCounts()
    byJobType[v.jobType]![v.verdict] += 1
    byWorkspace[v.workspaceId] ??= emptyVerdictCounts()
    byWorkspace[v.workspaceId]![v.verdict] += 1
  }

  const agentJobs = jobs.filter((j) => j.agentId === agentId)
  const typeCounts = new Map<string, number>()
  for (const j of agentJobs) {
    typeCounts.set(j.jobType, (typeCounts.get(j.jobType) ?? 0) + 1)
  }
  const commonJobTypes = [...typeCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([t]) => t)

  return {
    agentId,
    overall,
    byJobType,
    byWorkspace,
    totalJobs: agentJobs.length,
    commonJobTypes,
  }
}

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
import type { ApiAdapter, NewGuardrailInput } from './types'

/**
 * Placeholder HTTP adapter for future FastAPI wiring.
 * Methods throw until `/api/*` endpoints exist.
 */
export class HttpAdapter implements ApiAdapter {
  private readonly baseUrl: string

  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    })
    if (res.status === 404) {
      return undefined as T
    }
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      throw new Error(`HttpAdapter ${path} failed: ${res.status} ${body}`)
    }
    if (res.status === 204) {
      return true as T
    }
    return (await res.json()) as T
  }

  getState(): Promise<DemoState> {
    return this.request<DemoState>('/demo/state')
  }

  clearAllData(): Promise<DemoState> {
    return this.request<DemoState>('/demo/state', { method: 'DELETE' })
  }

  ingestContext(raw: string, source: 'paste' | 'upload'): Promise<ContextDocument> {
    return this.request<ContextDocument>('/context/ingest', {
      method: 'POST',
      body: JSON.stringify({ raw, source }),
    })
  }

  listWorkspaces(): Promise<Workspace[]> {
    return this.request<Workspace[]>('/workspaces')
  }

  listRuns(): Promise<Run[]> {
    return this.request<Run[]>('/runs')
  }

  getRun(runId: string): Promise<Run | undefined> {
    return this.request<Run | undefined>(`/runs/${runId}`)
  }

  startRun(input: import('./types').StartRunInput): Promise<Run> {
    return this.request<Run>('/runs', {
      method: 'POST',
      body: JSON.stringify({
        title: input.title,
        objectives: input.objectives ?? [],
        workspace_ids: input.workspaceIds,
        plan: input.plan ?? [],
        signal: input.signal ?? {},
      }),
    })
  }

  listJobs(runId?: string): Promise<Job[]> {
    const q = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
    return this.request<Job[]>(`/jobs${q}`)
  }

  listTimeline(runId: string): Promise<TimelineEvent[]> {
    return this.request<TimelineEvent[]>(`/runs/${runId}/timeline`)
  }

  listApprovals(decision?: ApprovalDecision): Promise<ApprovalItem[]> {
    const q = decision ? `?decision=${decision}` : ''
    return this.request<ApprovalItem[]>(`/approvals${q}`)
  }

  decideApproval(
    approvalId: string,
    decision: Exclude<ApprovalDecision, 'pending'>,
    editedPayload?: string,
  ): Promise<ApprovalItem | undefined> {
    return this.request<ApprovalItem | undefined>(`/approvals/${approvalId}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, editedPayload }),
    })
  }

  listPolicies(): Promise<WorkspacePolicy[]> {
    return this.request<WorkspacePolicy[]>('/policies')
  }

  updatePolicy(
    workspaceId: string,
    action: string,
    patch: Partial<Pick<WorkspacePolicy['actions'][number], 'allowed' | 'hilRequired' | 'autoMerge'>>,
  ): Promise<WorkspacePolicy | undefined> {
    return this.request<WorkspacePolicy | undefined>(
      `/policies/${workspaceId}/${encodeURIComponent(action)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      },
    )
  }

  listIntegrations(): Promise<IntegrationHealth[]> {
    return this.request<{ integrations?: IntegrationHealth[] } | IntegrationHealth[]>(
      '/integrations/health',
    ).then((body) => (Array.isArray(body) ? body : (body.integrations ?? [])))
  }

  listValidations(): Promise<ValidationOutcome[]> {
    return this.request<ValidationOutcome[]>('/validations')
  }

  listAgents(): Promise<Agent[]> {
    return this.request<Agent[]>('/agents')
  }

  getAgent(agentId: string): Promise<Agent | undefined> {
    return this.request<Agent | undefined>(`/agents/${agentId}`)
  }

  getAgentMetrics(agentId: string): Promise<AgentMetrics | undefined> {
    return this.request<AgentMetrics | undefined>(`/agents/${agentId}/metrics`)
  }

  addAgentGuardrail(agentId: string, input: NewGuardrailInput): Promise<AgentGuardrail | undefined> {
    return this.request<AgentGuardrail | undefined>(`/agents/${agentId}/guardrails`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  updateAgentGuardrail(
    agentId: string,
    guardrailId: string,
    patch: Partial<Pick<AgentGuardrail, 'mode' | 'label' | 'rationale' | 'tool'>>,
  ): Promise<AgentGuardrail | undefined> {
    return this.request<AgentGuardrail | undefined>(`/agents/${agentId}/guardrails/${guardrailId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
  }

  removeAgentGuardrail(agentId: string, guardrailId: string): Promise<boolean> {
    return this.request<boolean>(`/agents/${agentId}/guardrails/${guardrailId}`, {
      method: 'DELETE',
    })
  }
}

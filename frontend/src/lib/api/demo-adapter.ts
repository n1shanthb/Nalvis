import { createEmptyState, parseContextInput } from '@/lib/demo/seed'
import type {
  AgentGuardrail,
  ApprovalDecision,
  ApprovalItem,
  ContextDocument,
  DemoState,
  WorkspacePolicy,
} from '@/lib/demo/models'
import { computeAgentMetrics, type ApiAdapter, type NewGuardrailInput } from './types'

/**
 * In-memory local store. Starts empty — never invents runs/agents/approvals.
 * Wire HttpAdapter when the API exists.
 */
export class DemoAdapter implements ApiAdapter {
  private state: DemoState

  constructor(initial?: DemoState) {
    this.state = initial ?? createEmptyState()
  }

  async getState() {
    return structuredClone(this.state)
  }

  async ingestContext(raw: string, source: 'paste' | 'upload'): Promise<ContextDocument> {
    const doc = parseContextInput(raw, source)
    this.state.contextDocuments = [doc, ...this.state.contextDocuments]
    if (doc.parsePreview?.products.length && !this.state.companyName) {
      try {
        const parsed = JSON.parse(raw) as { company?: string }
        if (parsed.company) this.state.companyName = parsed.company
      } catch {
        /* ignore */
      }
    }
    return structuredClone(doc)
  }

  async listWorkspaces() {
    return structuredClone(this.state.workspaces)
  }

  async listRuns() {
    return structuredClone(this.state.runs)
  }

  async getRun(runId: string) {
    return structuredClone(this.state.runs.find((r) => r.id === runId))
  }

  async listJobs(runId?: string) {
    const jobs = runId ? this.state.jobs.filter((j) => j.runId === runId) : this.state.jobs
    return structuredClone(jobs)
  }

  async listTimeline(runId: string) {
    return structuredClone(
      this.state.timeline.filter((t) => t.runId === runId).sort((a, b) => a.at.localeCompare(b.at)),
    )
  }

  async listApprovals(decision?: ApprovalDecision) {
    const items = decision
      ? this.state.approvals.filter((a) => a.decision === decision)
      : this.state.approvals
    return structuredClone(items)
  }

  async decideApproval(
    approvalId: string,
    decision: Exclude<ApprovalDecision, 'pending'>,
    editedPayload?: string,
  ): Promise<ApprovalItem | undefined> {
    const item = this.state.approvals.find((a) => a.id === approvalId)
    if (!item) return undefined
    item.decision = decision
    item.decidedAt = new Date().toISOString()
    if (decision === 'edited' && editedPayload !== undefined) {
      item.editedPayload = editedPayload
      item.diffPreview.after = editedPayload
    }
    const job = this.state.jobs.find((j) => j.id === item.jobId)
    if (job) {
      if (decision === 'denied') {
        job.status = 'failed'
        job.error = 'Denied by human approver'
        job.finishedAt = item.decidedAt
      } else {
        job.status = 'succeeded'
        job.finishedAt = item.decidedAt
        job.error = null
      }
    }
    return structuredClone(item)
  }

  async listPolicies() {
    return structuredClone(this.state.policies)
  }

  async updatePolicy(
    workspaceId: string,
    action: string,
    patch: Partial<Pick<WorkspacePolicy['actions'][number], 'allowed' | 'hilRequired' | 'autoMerge'>>,
  ) {
    const policy = this.state.policies.find((p) => p.workspaceId === workspaceId)
    if (!policy) return undefined
    const row = policy.actions.find((a) => a.action === action)
    if (!row) return undefined
    Object.assign(row, patch)
    if (patch.autoMerge === true) row.hilRequired = false
    if (patch.hilRequired === true) row.autoMerge = false
    return structuredClone(policy)
  }

  async listIntegrations() {
    return structuredClone(this.state.integrations)
  }

  async listValidations() {
    return structuredClone(this.state.validations)
  }

  async listAgents() {
    return structuredClone(this.state.agents)
  }

  async getAgent(agentId: string) {
    return structuredClone(this.state.agents.find((a) => a.id === agentId))
  }

  async getAgentMetrics(agentId: string) {
    if (!this.state.agents.some((a) => a.id === agentId)) return undefined
    return computeAgentMetrics(agentId, this.state.validations, this.state.jobs)
  }

  async addAgentGuardrail(agentId: string, input: NewGuardrailInput) {
    const agent = this.state.agents.find((a) => a.id === agentId)
    if (!agent) return undefined
    const modeLabel =
      input.mode === 'hil'
        ? 'Require HIL'
        : input.mode === 'deny'
          ? 'Deny'
          : input.mode === 'auto'
            ? 'Auto-run'
            : 'Allow'
    const rule: AgentGuardrail = {
      id: `gr-user-${Date.now()}`,
      tool: input.tool,
      mode: input.mode,
      label: input.label?.trim() || `${modeLabel} · ${input.tool}`,
      rationale: input.rationale?.trim() || 'Added by operator from agent profile.',
      source: 'user',
      createdAt: new Date().toISOString(),
    }
    agent.guardrails = [rule, ...agent.guardrails]
    return structuredClone(rule)
  }

  async updateAgentGuardrail(
    agentId: string,
    guardrailId: string,
    patch: Partial<Pick<AgentGuardrail, 'mode' | 'label' | 'rationale' | 'tool'>>,
  ) {
    const agent = this.state.agents.find((a) => a.id === agentId)
    const rule = agent?.guardrails.find((g) => g.id === guardrailId)
    if (!rule) return undefined
    Object.assign(rule, patch)
    return structuredClone(rule)
  }

  async removeAgentGuardrail(agentId: string, guardrailId: string) {
    const agent = this.state.agents.find((a) => a.id === agentId)
    if (!agent) return false
    const before = agent.guardrails.length
    agent.guardrails = agent.guardrails.filter((g) => g.id !== guardrailId)
    return agent.guardrails.length < before
  }

  /** Test helper — wipe local store back to empty. */
  reset() {
    this.state = createEmptyState()
  }
}

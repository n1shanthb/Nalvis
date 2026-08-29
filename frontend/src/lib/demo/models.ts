/** Canonical frontend domain models aligned with AUTHORITY.md nouns. */

export type ValidationVerdict = 'PASS' | 'FAIL' | 'NO_EVIDENCE'

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'partial'

export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'blocked_for_approval'

export type AgentStatus = 'active' | 'idle' | 'disabled' | 'error' | 'unsupported'

export type IntegrationName = 'github' | 'jira' | 'gmail' | 'calendar'

export type IntegrationHealthStatus = 'healthy' | 'degraded' | 'down' | 'unknown'

export type ApprovalDecision = 'pending' | 'approved' | 'denied' | 'edited'

export interface WorkspaceScope {
  repos: string[]
  jiraKeys: string[]
  calendars: string[]
  emailGroups: string[]
}

export interface Workspace {
  id: string
  name: string
  product: string
  description: string
  scope: WorkspaceScope
  createdAt: string
}

export interface ContextDocument {
  id: string
  name: string
  source: 'paste' | 'upload'
  raw: string
  parsedAt: string | null
  workspaceIds: string[]
  parsePreview: ParsePreview | null
}

export interface ParsePreview {
  products: string[]
  workspacesDerived: number
  repos: string[]
  jiraProjects: string[]
  calendars: string[]
  emailGroups: string[]
  stakeholders: string[]
  warnings: string[]
}

export interface Evidence {
  jobType: string
  refs: Record<string, string>
  collectedAt: string
}

export interface ValidationCheck {
  name: string
  passed: boolean
  detail: string
}

export interface ValidationOutcome {
  id: string
  jobId: string
  runId: string
  workspaceId: string
  agentId: string
  jobType: string
  verdict: ValidationVerdict
  confidence: number
  message: string
  reasoning: string
  checks: ValidationCheck[]
  evidence: Evidence | null
  checkedAt: string
}

export interface Job {
  id: string
  runId: string
  workspaceId: string
  agentId: string
  jobType: string
  title: string
  status: JobStatus
  requestedAction: Record<string, unknown>
  error: string | null
  startedAt: string | null
  finishedAt: string | null
  validationId: string | null
  approvalId: string | null
}

export interface TimelineEvent {
  id: string
  runId: string
  jobId: string | null
  kind: 'queued' | 'started' | 'approval' | 'tool_call' | 'validation' | 'completed' | 'failed'
  label: string
  at: string
  meta?: Record<string, string>
}

export interface Run {
  id: string
  title: string
  status: RunStatus
  objectives: string[]
  workspaceIds: string[]
  temporalWorkflowId: string
  createdAt: string
  updatedAt: string
  jobIds: string[]
}

export interface ApprovalItem {
  id: string
  jobId: string
  runId: string
  workspaceId: string
  agentId: string
  jobType: string
  title: string
  intentSummary: string
  diffPreview: { before: string; after: string }
  decision: ApprovalDecision
  editedPayload: string | null
  createdAt: string
  decidedAt: string | null
}

export interface ActionPolicy {
  action: string
  label: string
  allowed: boolean
  hilRequired: boolean
  autoMerge: boolean
}

export interface WorkspacePolicy {
  workspaceId: string
  actions: ActionPolicy[]
}

export type IntegrationTransport = 'mcp' | 'native' | 'mcp+app'

export interface IntegrationHealth {
  name: IntegrationName
  displayName: string
  status: IntegrationHealthStatus
  credentialsConfigured: boolean
  lastSuccessfulCallAt: string | null
  lastError: string | null
  rateLimitRemaining: number | null
  rateLimitResetAt: string | null
  latencyMsP50: number | null
  /** ISO timestamp from control plane health check */
  checkedAt?: string | null
  transport?: IntegrationTransport
  /** Non-secret connector settings (flags, URLs, smoke targets) */
  config?: Record<string, string | number | boolean | null | undefined>
}

export type GuardrailMode = 'allow' | 'hil' | 'deny' | 'auto'
export type GuardrailSource = 'synthesized' | 'user'

export interface AgentOriginEvidence {
  contextDocumentId: string
  contextDocumentName: string
  rationale: string
  kgPaths: string[]
  signals: string[]
  synthesizedAt: string
}

export interface AgentSpecs {
  runtime: string
  modelHint: string
  maxConcurrency: number
  timeoutSec: number
  memoryKeys: string[]
  inputSchema: string[]
  outputSchema: string[]
  leastPrivilegeNote: string
}

export interface AgentGuardrail {
  id: string
  tool: string
  mode: GuardrailMode
  label: string
  rationale: string
  source: GuardrailSource
  createdAt: string
}

export interface Agent {
  id: string
  name: string
  role: string
  description: string
  mission: string
  toolScope: string[]
  workspaceIds: string[]
  status: AgentStatus
  createdAt: string
  lastActiveAt: string
  origin: AgentOriginEvidence
  specs: AgentSpecs
  guardrails: AgentGuardrail[]
}

export interface AgentMetrics {
  agentId: string
  overall: Record<ValidationVerdict, number>
  byJobType: Record<string, Record<ValidationVerdict, number>>
  byWorkspace: Record<string, Record<ValidationVerdict, number>>
  totalJobs: number
  commonJobTypes: string[]
}

export interface DemoState {
  companyName: string
  contextDocuments: ContextDocument[]
  workspaces: Workspace[]
  runs: Run[]
  jobs: Job[]
  timeline: TimelineEvent[]
  approvals: ApprovalItem[]
  policies: WorkspacePolicy[]
  integrations: IntegrationHealth[]
  validations: ValidationOutcome[]
  agents: Agent[]
}

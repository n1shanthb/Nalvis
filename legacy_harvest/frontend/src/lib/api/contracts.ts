export interface ApiEnvelope { ok: boolean; message?: string; }
export interface ActivityEvent { id: string; type: string; source: string; message: string; employee?: string; spec_id?: string | null; connected_system_id?: string | null; payload: Record<string, unknown>; created_at: string; }
export interface ProjectSummary { id: string; name: string; source: string; entities: number; relationships: number; }
export interface DashboardResponse extends ApiEnvelope { projects: ProjectSummary[]; stats: { projects: number; entities: number; mcps: number; mcp_total: number; tools: number; events_today: number }; events: ActivityEvent[]; }
export interface ProjectOverview { project_id: string; name: string; entities: number; relationships: number; entity_types: string[]; relationship_types: string[]; top_labels: [string, number][]; mcp_connected: number; mcp_total: number; tool_count: number; }
export interface ProjectResponse extends ApiEnvelope { project: ProjectOverview; }
export interface CreateProjectResponse extends ApiEnvelope {
  project_id: string;
  project_ids?: string[];
}

export interface DepartmentResponsibility {
  capability_id: string;
  label: string;
  purpose?: string;
  evidence_entity_ids?: string[];
  evidence_paths?: Array<{ hops: Array<{ entity_id: string; entity_name?: string; via_relationship?: string | null }> }>;
  confidence: number;
}

export interface OrganizationDepartment {
  id: string;
  name: string;
  purpose: string;
  source: string;
  confidence: number;
  leader_role?: string | null;
  leader_entity_id?: string | null;
  responsibilities: DepartmentResponsibility[];
  children: OrganizationDepartment[];
}

export interface CapabilityCluster {
  capability_id: string;
  label: string;
  purpose?: string;
  reasoning?: string;
}

export interface ValidationIssue { code: string; message: string; capability_id?: string | null; }
export interface UnsupportedCluster { capability_id: string; label: string; reason: string; }

export interface OrganizationModel {
  org_id: string;
  generation_source: string;
  intent: { clusters: CapabilityCluster[] };
  departments: OrganizationDepartment[];
  validation: {
    unsupported_clusters: UnsupportedCluster[];
    missing_evidence: ValidationIssue[];
    conflicts: ValidationIssue[];
  };
}

export interface OrganizationResponse extends ApiEnvelope {
  organization: OrganizationModel | null;
  entity_names?: Record<string, string>;
  cached?: boolean;
}

export interface WorkforceRole {
  role_id: string;
  title: string;
  purpose: string;
  description?: string;
  reports_to?: string | null;
  team_id: string;
  responsibilities: string[];
  required_knowledge?: string[];
  evidence_entity_ids: string[];
  confidence: number;
  review_status: string;
}

export interface TeamPlan {
  team_id: string;
  name: string;
  purpose: string;
  source: string;
  responsibilities: string[];
  lead_role_id?: string | null;
  missing_responsibility_ids?: string[];
  workforce_roles: WorkforceRole[];
}

export interface PlanningHealth {
  health_percent: number;
  coverage_percent: number;
  missing_responsibilities?: number;
  overloaded_teams?: number;
  ai_roles_needed?: number;
}

export interface DepartmentStrategy {
  owned_responsibility_ids: string[];
}

export interface DepartmentPlan {
  department_id: string;
  department_name: string;
  planning_status: string;
  purpose?: string;
  summary: string;
  leader_entity_id?: string | null;
  leader_role?: string | null;
  confidence: number;
  strategy: DepartmentStrategy;
  teams: TeamPlan[];
  workforce_roles: WorkforceRole[];
  health: PlanningHealth;
}

export interface PlanningDiagnostic {
  headline: string;
  detail: string;
  suggestion?: string;
  action_href?: string;
  action_label?: string;
}

export interface DepartmentsResponse extends ApiEnvelope {
  departments: DepartmentPlan[];
  diagnostics?: Record<string, PlanningDiagnostic>;
  entity_names?: Record<string, string>;
}

export interface DepartmentResponse extends ApiEnvelope {
  department: DepartmentPlan;
  entity_names?: Record<string, string>;
  diagnostic?: PlanningDiagnostic | null;
}

export interface DepartmentCapability {
  capability_id: string;
  name: string;
  description?: string;
  owner_role_ids: string[];
  team_ids: string[];
  evidence_ids: string[];
  confidence: number;
  review_status: string;
}

export interface CapabilityCatalogResponse extends ApiEnvelope {
  catalog: {
    capabilities: DepartmentCapability[];
    health: { capability_count: number };
  };
}

export interface DepartmentWorkflow {
  workflow_id: string;
  name: string;
  description?: string;
  owner_team_ids: string[];
  capability_ids: string[];
  evidence_ids: string[];
  knowledge_ids: string[];
  confidence: number;
  review_status: string;
}

export interface WorkflowCatalogResponse extends ApiEnvelope {
  catalog: {
    workflows: DepartmentWorkflow[];
    health: { workflow_count: number };
  };
}

export interface DiscoveryOpportunity {
  title: string;
  department: string;
  department_id?: string;
  team_id?: string;
  team_name?: string;
  system: string;
  estimated_value: string;
  description: string;
  role?: string;
  role_id?: string;
  workflow_id?: string;
  required_intents?: Array<{ system: string; access: string; action: string }>;
}

export interface SpecGuardrail {
  id?: string;
  label?: string | null;
  action: string;
  effect: "allow" | "deny" | "require_approval";
  reason?: string | null;
  policy_scope?: string | null;
}

export interface DiscoveryAgent {
  spec_id: string;
  title: string;
  valid: boolean;
  approval_status: string;
  redundancy_status?: string;
  spec_version?: number;
  redundancy_reason?: string;
  previous_spec_id?: string | null;
  next_spec_id?: string | null;
  last_approved_spec_id?: string | null;
  tools: string[];
  guardrails?: Array<string | SpecGuardrail>;
  department?: string;
  department_id?: string;
  team_id?: string;
  team_name?: string;
  role?: string;
  role_id?: string;
  workflow_id?: string;
  connected_system_ids?: string[];
}

export interface DiscoveryResponse extends ApiEnvelope {
  result?: {
    duration_seconds: number;
    analysis: { automation_opportunities: DiscoveryOpportunity[] };
    agents: DiscoveryAgent[];
  };
  error?: string;
}

export interface AgentSpec {
  agent: { id?: string; title: string; org_id?: string };
  goal: string;
  tools?: string[];
  permissions?: string[];
  guardrails?: Array<string | SpecGuardrail>;
  metadata?: Record<string, unknown>;
  runtime?: { adapter?: string; profile?: string; config?: Record<string, unknown> };
  execution?: { mode?: string; max_steps?: number };
  trigger?: { type?: string; webhook_ids?: string[] };
}

export interface WakeWebhook {
  id: string;
  connected_system_id: string;
  event: string;
  action?: string;
  description?: string;
}

export interface AgentSpecProfileResponse extends ApiEnvelope {
  spec: AgentSpec;
  yaml: string;
  marketplace: Record<string, Tool[]>;
  assigned_keys: string[];
  available_webhooks?: WakeWebhook[];
}
export interface Tool { name: string; description: string; toolset?: string; }
export interface McpSummary { total: number; connected: number; configured: number; }
export interface McpSystem { id: string; display_name: string; description: string; status: string; health: string; configured: boolean; tool_count: number; mcp_url: string; toolsets: string; tools: Tool[]; webhooks: Array<{ id: string; event: string; action?: string; description: string }>; bindings?: Array<{ webhook_id: string; spec_id: string; enabled?: boolean }>; }
export interface McpsResponse extends ApiEnvelope { summary: McpSummary; systems: McpSystem[]; }
export interface McpResponse extends ApiEnvelope { system: McpSystem; }
export interface AgentListItem {
  spec_id: string;
  title: string;
  goal?: string;
  tools: string[];
  systems?: string[];
  approval_status?: string;
  org_id?: string;
  company_id?: string | null;
  project_id?: string | null;
  discovered_from?: string | null;
  scope_level?: string;
  department?: string | null;
  team_name?: string | null;
  role?: string | null;
}
export interface AgentsResponse extends ApiEnvelope { agents: AgentListItem[]; }
export interface AgentResponse extends ApiEnvelope { spec: AgentSpec; marketplace: Record<string, Tool[]>; assigned_keys: string[]; yaml?: string; }
export interface SystemReadiness {
  required: boolean;
  configured: boolean;
  ready: boolean;
  app_installed?: boolean;
  mailbox?: string;
  watch_active?: boolean;
  watch_error?: string;
  topic_configured?: boolean;
  error?: string;
}
export interface AgentReadiness extends ApiEnvelope {
  spec_id: string;
  title: string;
  systems: string[];
  inbound_systems: string[];
  ready: boolean;
  github: SystemReadiness;
  gmail: SystemReadiness;
  jira: SystemReadiness;
  calendar: SystemReadiness;
  tunnel: {
    running: boolean;
    status: string;
    urls: Record<string, string>;
    url_changed?: boolean;
    error?: string;
    binary?: boolean;
    install_hint?: string | null;
  };
}
export interface CalendarResponse extends ApiEnvelope { configured: boolean; month_label: string; calendars: Array<{ id: string; summary?: string }>; matrix: string[][]; by_day?: Record<string, Array<{ id: string; summary?: string; html_link?: string }>>; previous?: { year: number; month: number }; next?: { year: number; month: number }; }
export interface MonitorResponse extends ApiEnvelope { events: ActivityEvent[]; }
export interface LabResponse extends ApiEnvelope { configured: boolean; tools: Tool[]; }
export interface ValidationCheckMarks {
  outcome: string;
  response_sla: string;
  guardrail_bypass: string;
  log_ok: string;
}
export interface ValidationRecordDto {
  execution_id?: string | null;
  watch_id?: string | null;
  spec_id: string;
  project_id: string;
  system: string;
  objective: string;
  verdict: string;
  confidence: number;
  claimed_action: string;
  expected: string;
  observed: string;
  check_marks: ValidationCheckMarks;
  evidence_refs: Record<string, unknown>;
  message: string;
  created_at?: string;
}
export interface ValidationsResponse extends ApiEnvelope { validations: ValidationRecordDto[]; }
export interface ValidationDetailResponse extends ApiEnvelope { validation: ValidationRecordDto; }

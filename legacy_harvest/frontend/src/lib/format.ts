import type { DepartmentPlan, TeamPlan, WorkforceRole } from "../lib/api/contracts";

export function confidenceLabel(score: number): string {
  if (score >= 0.7) return "High Confidence";
  if (score >= 0.5) return "Medium Confidence";
  if (score >= 0.3) return "Low Confidence";
  return "Needs Review";
}

export function reviewLabel(status: string): string {
  return status.replaceAll("_", " ");
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function resolveReportsTo(reportsTo: string | null | undefined, entityNames: Record<string, string>): string {
  if (!reportsTo) return "—";
  if (reportsTo.startsWith("leader:")) return entityNames[reportsTo.slice(7)] ?? reportsTo.slice(7);
  if (reportsTo === "dept_head") return "Department head";
  return reportsTo;
}

export function resolveManager(team: TeamPlan, entityNames: Record<string, string>): string {
  for (const role of team.workforce_roles) {
    if (team.lead_role_id && role.role_id === team.lead_role_id && role.reports_to) {
      return resolveReportsTo(role.reports_to, entityNames);
    }
  }
  const first = team.workforce_roles[0];
  if (first?.reports_to) return resolveReportsTo(first.reports_to, entityNames);
  return "—";
}

export function teamStatus(team: TeamPlan): string {
  if (team.workforce_roles.length === 0) return "Empty";
  if (team.missing_responsibility_ids?.length) return "Gaps";
  return "Healthy";
}

export function teamSourceLabel(source: string): string {
  if (source === "recommended") return "Recommended team";
  if (source === "synthetic") return "Synthetic team";
  return "Team workspace";
}

export function needsAttention(plan: DepartmentPlan): boolean {
  return (
    plan.planning_status === "skipped" ||
    (plan.health.missing_responsibilities ?? 0) > 0 ||
    (plan.health.overloaded_teams ?? 0) > 0 ||
    (plan.health.ai_roles_needed ?? 0) > 0
  );
}

export const actionableReview = new Set(["proposed", "needs_review", "changes_requested"]);

export function isActionableRole(role: WorkforceRole): boolean {
  return actionableReview.has(role.review_status);
}

export const sourceLabels: Record<string, string> = {
  graph: "In your org chart",
  inferred: "Suggested",
  llm_assisted: "Suggested",
};

export const generationLabels: Record<string, string> = {
  deterministic: "Built from your company data",
  llm_assisted: "AI-assisted from your company data",
};

export function countOwnedDepartments(departments: Array<{ responsibilities: unknown[]; children?: unknown[] }>): number {
  let count = 0;
  for (const dept of departments) {
    if (dept.responsibilities.length > 0 || (dept.children?.length ?? 0) > 0) count += 1;
  }
  return count;
}

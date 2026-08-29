export type SpecGuardrail = {
  id?: string;
  label?: string | null;
  action: string;
  effect: "allow" | "deny" | "require_approval";
  reason?: string | null;
  policy_scope?: string | null;
};

export function asRails(raw: unknown): SpecGuardrail[] {
  if (!Array.isArray(raw)) return [];
  const out: SpecGuardrail[] = [];
  for (const item of raw) {
    if (typeof item === "string") {
      out.push({ label: item, action: "*", effect: "allow", reason: null });
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const effectRaw = String(row.effect || "allow");
    const effect: SpecGuardrail["effect"] =
      effectRaw === "deny" || effectRaw === "require_approval" || effectRaw === "allow"
        ? effectRaw
        : "allow";
    out.push({
      id: typeof row.id === "string" ? row.id : undefined,
      label: typeof row.label === "string" ? row.label : null,
      action: String(row.action || "*"),
      effect,
      reason: typeof row.reason === "string" ? row.reason : null,
      policy_scope: typeof row.policy_scope === "string" ? row.policy_scope : "agent",
    });
  }
  return out;
}

export function railLabel(rail: SpecGuardrail): string {
  return rail.label || rail.id || rail.action || "rail";
}

export function railPayload(rails: SpecGuardrail[]) {
  return rails.map(rail => ({
    id: rail.id,
    label: railLabel(rail),
    action: rail.action || "*",
    effect: rail.effect,
    reason: rail.reason || undefined,
    policy_scope: "agent",
  }));
}

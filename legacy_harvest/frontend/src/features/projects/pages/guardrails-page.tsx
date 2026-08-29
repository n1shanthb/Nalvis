import { useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Btn, Chip, EmptyState, PageHead, Panel, StatRow } from "../../../components/ui";
import type { DiscoveryAgent } from "../../../lib/api/contracts";
import { api } from "../../../lib/api";
import { titleCase } from "../../../lib/format";
import { QueryBoundary } from "../../../lib/query";
import { useDiscovery } from "../hooks/projects.hooks";
import { GuardrailDiscoverySection } from "./guardrail-discovery";
import { asRails, railPayload, type SpecGuardrail } from "../guardrail-rails";

function effectTone(effect: string): "" | "good" | "bad" | "accent" | "warning" {
  if (effect === "deny") return "bad";
  if (effect === "require_approval") return "warning";
  if (effect === "allow") return "accent";
  return "";
}

function AddRailForm({
  tools,
  onAdd,
  onCancel,
}: {
  tools: string[];
  onAdd: (rail: SpecGuardrail) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState("");
  const [action, setAction] = useState(tools[0] || "*");
  const [effect, setEffect] = useState<SpecGuardrail["effect"]>("require_approval");
  const [reason, setReason] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const cleanLabel = label.trim() || `rail_${action}`;
    onAdd({
      label: cleanLabel,
      action: action || "*",
      effect: action === "*" ? "allow" : effect,
      reason: reason.trim() || null,
      policy_scope: "agent",
    });
  }

  return (
    <form className="guardrail-form" onSubmit={submit}>
      <label>
        Label
        <input value={label} onChange={e => setLabel(e.target.value)} placeholder="never_merge_without_review" required />
      </label>
      <label>
        Tool action
        <select value={action} onChange={e => setAction(e.target.value)}>
          <option value="*">* (prompt-only)</option>
          {tools.map(tool => (
            <option key={tool} value={tool}>
              {tool}
            </option>
          ))}
        </select>
      </label>
      <label>
        Effect
        <select
          value={effect}
          onChange={e => setEffect(e.target.value as SpecGuardrail["effect"])}
          disabled={action === "*"}
        >
          <option value="require_approval">Require approval</option>
          <option value="deny">Deny</option>
          <option value="allow">Allow (advisory)</option>
        </select>
      </label>
      <label>
        Reason
        <input value={reason} onChange={e => setReason(e.target.value)} placeholder="Why this rule exists" />
      </label>
      <div className="form-inline">
        <Btn type="submit" className="primary">
          Add
        </Btn>
        <Btn type="button" className="ghost" onClick={onCancel}>
          Cancel
        </Btn>
      </div>
    </form>
  );
}

function AgentGuardrailCard({
  projectId,
  agent,
}: {
  projectId: string;
  agent: DiscoveryAgent & { guardrails?: unknown };
}) {
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const rails = useMemo(() => asRails(agent.guardrails), [agent.guardrails]);
  const patch = useMutation({
    mutationFn: (next: SpecGuardrail[]) =>
      api(`/projects/${projectId}/discovery/specs/${encodeURIComponent(agent.spec_id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guardrails: railPayload(next) }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["projects", "discovery", projectId] }),
  });

  function save(next: SpecGuardrail[]) {
    patch.mutate(next);
  }

  return (
    <article className="team-card">
      <div className="team-card-head">
        <div>
          <p className="surface-label">{agent.department || "Organization"}{agent.team_name ? ` · ${agent.team_name}` : ""}</p>
          <h3>{agent.title}</h3>
          <p className="muted">
            <code>{agent.spec_id}</code>
          </p>
        </div>
        <div className="tag-row">
          <Chip soft>{rails.length} rails</Chip>
          <Chip soft>{agent.tools.length} tools</Chip>
          <Chip tone={agent.approval_status === "active" ? "good" : agent.approval_status === "approved" ? "accent" : "warning"}>
            {titleCase(agent.approval_status)}
          </Chip>
        </div>
      </div>

      {rails.length ? (
        <div className="spec-list">
          {rails.map((rail, index) => (
            <article className="spec-card" key={rail.id || `${rail.label}-${rail.action}-${index}`}>
              <div className="spec-card-head">
                <div>
                  <h3>{rail.label || rail.id || rail.action || "rail"}</h3>
                  <p className="spec-card-id">
                    <code>{rail.action}</code>
                    {rail.reason ? <span className="muted"> — {rail.reason}</span> : null}
                  </p>
                </div>
                <div className="tag-row">
                  <Chip tone={effectTone(rail.effect)}>{titleCase(rail.effect)}</Chip>
                  {rail.action !== "*" && (rail.effect === "deny" || rail.effect === "require_approval") ? (
                    <Chip tone="good">Enforced</Chip>
                  ) : (
                    <Chip soft>Prompt-only</Chip>
                  )}
                </div>
              </div>
              <div className="spec-card-actions">
                <label className="guardrail-inline">
                  Effect
                  <select
                    value={rail.effect}
                    disabled={patch.isPending || rail.action === "*"}
                    onChange={e => {
                      const effect = e.target.value as SpecGuardrail["effect"];
                      save(rails.map((item, i) => (i === index ? { ...item, effect } : item)));
                    }}
                  >
                    <option value="require_approval">Require approval</option>
                    <option value="deny">Deny</option>
                    <option value="allow">Allow</option>
                  </select>
                </label>
                <Btn
                  className="ghost"
                  disabled={patch.isPending}
                  onClick={() => save(rails.filter((_, i) => i !== index))}
                >
                  Remove
                </Btn>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No guardrails yet" description="Add a tool-bound rule — it writes to YAML and syncs to runtime policies." />
      )}

      {adding ? (
        <AddRailForm
          tools={agent.tools}
          onCancel={() => setAdding(false)}
          onAdd={rail => {
            setAdding(false);
            save([...rails, rail]);
          }}
        />
      ) : (
        <div className="toolbar">
          <Btn className="accent" disabled={patch.isPending} onClick={() => setAdding(true)}>
            Add guardrail
          </Btn>
          {patch.isError ? <span className="muted">{(patch.error as Error).message}</span> : null}
          {patch.isSuccess ? <span className="muted">Saved to YAML</span> : null}
        </div>
      )}
    </article>
  );
}

function AgentGuardrailsPanel({ projectId, agents }: { projectId: string; agents: Array<DiscoveryAgent & { guardrails?: unknown }> }) {
  const enforceable = agents.reduce((n, agent) => {
    return n + asRails(agent.guardrails).filter(r => r.action !== "*" && (r.effect === "deny" || r.effect === "require_approval")).length;
  }, 0);

  return (
    <>
      <StatRow
        items={[
          [agents.length, "Agents"],
          [agents.reduce((n, a) => n + asRails(a.guardrails).length, 0), "YAML rails"],
          [enforceable, "Enforced at runtime"],
          [agents.reduce((n, a) => n + a.tools.length, 0), "Assigned tools"],
        ]}
      />
      <Panel title="Agent guardrails" hint="From each spec YAML — edits write back and sync policies">
        {agents.length ? (
          <div className="team-stack">
            {agents.map(agent => (
              <AgentGuardrailCard key={agent.spec_id} projectId={projectId} agent={agent} />
            ))}
          </div>
        ) : (
          <EmptyState title="No agents yet" description="Run discovery to generate agent specs with dynamic guardrails." />
        )}
      </Panel>
    </>
  );
}

export default function GuardrailsPage() {
  const { projectId = "" } = useParams();
  const discovery = useDiscovery(projectId);

  return (
    <>
      <PageHead
        eyebrow="Project admin"
        title="Guardrails"
        subtitle="Per-agent rails from YAML. Tool-bound deny / require_approval rules are enforced at runtime."
      />

      <GuardrailDiscoverySection projectId={projectId} />

      <QueryBoundary query={discovery}>
        {data => (
          <AgentGuardrailsPanel
            projectId={projectId}
            agents={(data.result?.agents ?? []) as Array<DiscoveryAgent & { guardrails?: unknown }>}
          />
        )}
      </QueryBoundary>

      <details className="surface card-inset">
        <summary className="surface-title">Legacy project toggles (not enforced)</summary>
        <p className="muted">
          Project policy checkboxes and role permissions are not wired to runtime. Manage real enforcement via per-agent YAML rails above or Guardrail Discovery suggestions.
        </p>
      </details>
    </>
  );
}

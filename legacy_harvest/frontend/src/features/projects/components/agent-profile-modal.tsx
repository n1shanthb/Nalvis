import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Btn, Chip, EmptyState, ErrorState, Loading } from "../../../components/ui";
import { titleCase } from "../../../lib/format";
import { asRails, railLabel, railPayload, type SpecGuardrail } from "../guardrail-rails";
import { useAgentLifecycle, usePatchGeneratedSpec, useSpecProfile } from "../hooks/projects.hooks";

type Tab = "overview" | "tools" | "guardrails" | "yaml";

function metaString(meta: Record<string, unknown> | undefined, key: string): string {
  const value = meta?.[key];
  return typeof value === "string" ? value : "";
}

export function AgentProfileModal({
  projectId,
  specId,
  onClose,
}: {
  projectId: string;
  specId: string;
  onClose: () => void;
}) {
  const profile = useSpecProfile(projectId, specId);
  const lifecycle = useAgentLifecycle(projectId);
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const busy = lifecycle.isPending ? lifecycle.variables?.action ?? null : null;

  function run(action: "approve" | "activate" | "delete") {
    lifecycle.mutate(
      { specId, action },
      {
        onSuccess: () => {
          if (action === "delete") onClose();
          if (action === "activate") {
            onClose();
            navigate(`/projects/${encodeURIComponent(projectId)}/runtime/${encodeURIComponent(specId)}?setup=1`);
          }
        },
      },
    );
  }

  return (
    <div className="profile-overlay" role="dialog" aria-modal="true" aria-labelledby="agent-profile-title">
      <div className="profile-modal">
        <button type="button" className="profile-close" onClick={onClose} aria-label="Close">
          Close
        </button>
        {profile.isPending ? (
          <Loading text="Loading agent profile…" />
        ) : profile.error ? (
          <ErrorState error={profile.error} />
        ) : profile.data ? (
          <ProfileBody
            projectId={projectId}
            specId={specId}
            data={profile.data}
            tab={tab}
            setTab={setTab}
            busy={busy}
            error={lifecycle.error}
            onAction={run}
          />
        ) : (
          <EmptyState title="Spec not found" description="This generated specification is no longer available." />
        )}
      </div>
    </div>
  );
}

function ProfileBody({
  projectId,
  specId,
  data,
  tab,
  setTab,
  busy,
  error,
  onAction,
}: {
  projectId: string;
  specId: string;
  data: NonNullable<ReturnType<typeof useSpecProfile>["data"]>;
  tab: Tab;
  setTab: (tab: Tab) => void;
  busy: string | null;
  error: Error | null;
  onAction: (action: "approve" | "activate" | "delete") => void;
}) {
  const patchSpec = usePatchGeneratedSpec(projectId, specId);
  const spec = data.spec;
  const meta = spec.metadata ?? {};
  const status = metaString(meta, "approval_status") || "draft";
  const redundancyStatus = metaString(meta, "redundancy_status") || "active";
  const redundancyReason = metaString(meta, "redundancy_reason");
  const specVersion = typeof meta.spec_version === "number" ? meta.spec_version : 1;
  const prevSpecId = metaString(meta, "previous_spec_id");
  const nextSpecId = metaString(meta, "next_spec_id");
  const lastApproved = metaString(meta, "last_approved_spec_id");

  const isRedundant = redundancyStatus === "redundant";
  const isActive = status === "active";
  const isApproved = status === "approved" || isActive;
  const canActivate = status === "approved";
  const hasNoNewer = !nextSpecId;
  const canApprove = status === "draft";
  const canDelete = (isRedundant && !isApproved) || (isRedundant && hasNoNewer);

  const department = metaString(meta, "department") || metaString(meta, "department_id");
  const team = metaString(meta, "team_name") || metaString(meta, "team_id");
  const role = metaString(meta, "role") || metaString(meta, "role_id");
  const workflow = metaString(meta, "workflow_id");
  const systems = Array.isArray(meta.connected_system_ids)
    ? (meta.connected_system_ids as unknown[]).map(String)
    : [];
  const tools = spec.tools ?? [];
  const rails = asRails(spec.guardrails);
  const permissions = spec.permissions ?? [];
  const selectedHooks = spec.trigger?.webhook_ids ?? [];
  const available = data.available_webhooks ?? [];
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("");
  const [action, setAction] = useState(tools[0] || "*");
  const [effect, setEffect] = useState<"allow" | "deny" | "require_approval">("require_approval");
  const [reason, setReason] = useState("");

  function toggleWebhook(id: string, checked: boolean) {
    const next = checked
      ? Array.from(new Set([...selectedHooks, id]))
      : selectedHooks.filter(item => item !== id);
    patchSpec.mutate({ trigger: { webhook_ids: next } });
  }

  function saveRails(next: SpecGuardrail[]) {
    patchSpec.mutate({
      guardrails: railPayload(
        next.map(rail => ({
          ...rail,
          effect: rail.action === "*" ? "allow" : rail.effect,
        })),
      ),
    });
  }

  return (
    <>
      <header className="profile-head">
        <p className="page-kicker">Agent profile</p>
        <h2 id="agent-profile-title">{spec.agent.title}</h2>
        <p className="muted truncate-id" title={spec.agent.id}>
          <code>{spec.agent.id}</code>
        </p>
        <div className="tag-row">
          {specVersion > 1 && <Chip soft>v{specVersion}</Chip>}
          <Chip tone={isActive ? "good" : isApproved ? "accent" : "warning"}>{titleCase(status)}</Chip>
          {isRedundant && <Chip tone="bad">Redundant</Chip>}
          {department && <Chip soft>{titleCase(department)}</Chip>}
          {team && <Chip soft>{team}</Chip>}
          <Chip soft>{tools.length} tools</Chip>
        </div>
      </header>

      <nav className="profile-tabs" aria-label="Profile sections">
        {(["overview", "tools", "guardrails", "yaml"] as Tab[]).map(item => (
          <button key={item} type="button" className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
            {item === "tools" ? "Tools & MCPs" : titleCase(item)}
          </button>
        ))}
      </nav>

      <div className="profile-body">
        {tab === "overview" && (
          <div className="profile-section">
            {redundancyReason && (
              <div
                style={{
                  marginBottom: "1rem",
                  padding: "0.75rem 1rem",
                  background: "var(--danger-soft)",
                  border: "1px solid color-mix(in srgb, var(--color-alert) 20%, transparent)",
                  borderRadius: "8px",
                }}
              >
                <p style={{ margin: 0, color: "var(--danger)", fontSize: "0.875rem" }}>
                  <strong>Redundancy Reason:</strong> {redundancyReason}
                </p>
              </div>
            )}
            <p className="lead">{spec.goal}</p>
            <dl className="meta-grid">
              <div>
                <dt>Version</dt>
                <dd>v{specVersion}</dd>
              </div>
              <div>
                <dt>Redundancy</dt>
                <dd>{titleCase(redundancyStatus)}</dd>
              </div>
              <div>
                <dt>Department</dt>
                <dd>{department || "—"}</dd>
              </div>
              <div>
                <dt>Team</dt>
                <dd>{team || "—"}</dd>
              </div>
              <div>
                <dt>Role</dt>
                <dd>{role || "—"}</dd>
              </div>
              <div>
                <dt>Workflow</dt>
                <dd>{workflow || "—"}</dd>
              </div>
              {prevSpecId && (
                <div className="meta-span-2">
                  <dt>Previous Version</dt>
                  <dd><code title={prevSpecId}>{prevSpecId}</code></dd>
                </div>
              )}
              {nextSpecId && (
                <div className="meta-span-2">
                  <dt>Next Version</dt>
                  <dd><code title={nextSpecId}>{nextSpecId}</code></dd>
                </div>
              )}
              {lastApproved && (
                <div className="meta-span-2">
                  <dt>Last Approved</dt>
                  <dd><code title={lastApproved}>{lastApproved}</code></dd>
                </div>
              )}
              <div>
                <dt>Runtime</dt>
                <dd>{spec.runtime?.adapter || "openai_agents"}</dd>
              </div>
              <div>
                <dt>Max steps</dt>
                <dd>{spec.execution?.max_steps ?? "—"}</dd>
              </div>
            </dl>
            <p className="surface-label">Permissions</p>
            <div className="tag-row">
              {permissions.length ? permissions.map(item => <Chip key={item} soft>{item}</Chip>) : <span className="muted">None</span>}
            </div>
          </div>
        )}

        {tab === "tools" && (
          <div className="profile-section">
            <p className="surface-label">Portable tools</p>
            <div className="tag-row">
              {tools.length ? tools.map(tool => <Chip key={tool}>{tool}</Chip>) : <span className="muted">None assigned yet</span>}
            </div>
            <p className="surface-label">Connected systems</p>
            <div className="tag-row">
              {systems.length ? systems.map(system => <Chip key={system} soft>{system}</Chip>) : <span className="muted">None</span>}
            </div>
            <p className="surface-label">Wake events</p>
            {available.length ? (
              <ul className="wake-list">
                {available.map(hook => (
                  <li key={hook.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={selectedHooks.includes(hook.id)}
                        disabled={patchSpec.isPending}
                        onChange={event => toggleWebhook(hook.id, event.target.checked)}
                      />
                      <code>{hook.id}</code>
                      <span className="muted">{hook.description}</span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : (
              <span className="muted">No webhook events for this spec’s systems.</span>
            )}
            <p className="muted">Assign more tools after activation on the Agents page.</p>
          </div>
        )}

        {tab === "guardrails" && (
          <div className="profile-section">
            <p className="lead">Edits write to the agent YAML and sync enforceable policies at runtime.</p>
            {rails.length ? (
              <div className="spec-list">
                {rails.map((rail, index) => (
                  <article className="spec-card" key={rail.id || `${railLabel(rail)}-${rail.action}-${index}`}>
                    <div className="spec-card-head">
                      <div>
                        <h3>{railLabel(rail)}</h3>
                        <p className="spec-card-id">
                          <code>{rail.action}</code>
                          {rail.reason ? <span className="muted"> — {rail.reason}</span> : null}
                        </p>
                      </div>
                      <Chip soft>{titleCase(rail.effect)}</Chip>
                    </div>
                    <div className="spec-card-actions">
                      <Btn
                        className="ghost"
                        disabled={patchSpec.isPending}
                        onClick={() => saveRails(rails.filter((_, i) => i !== index))}
                      >
                        Remove
                      </Btn>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="No guardrails" description="Add a tool-bound rule to enforce deny or require approval." />
            )}
            {adding ? (
              <form
                className="guardrail-form"
                onSubmit={event => {
                  event.preventDefault();
                  saveRails([
                    ...rails,
                    {
                      label: label.trim() || action,
                      action,
                      effect: action === "*" ? "allow" : effect,
                      reason: reason.trim() || null,
                      policy_scope: "agent",
                    },
                  ]);
                  setAdding(false);
                  setLabel("");
                  setReason("");
                }}
              >
                <label>
                  Label
                  <input value={label} onChange={e => setLabel(e.target.value)} required />
                </label>
                <label>
                  Tool
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
                  <select value={effect} onChange={e => setEffect(e.target.value as typeof effect)} disabled={action === "*"}>
                    <option value="require_approval">Require approval</option>
                    <option value="deny">Deny</option>
                    <option value="allow">Allow</option>
                  </select>
                </label>
                <label>
                  Reason
                  <input value={reason} onChange={e => setReason(e.target.value)} />
                </label>
                <div className="form-inline">
                  <Btn type="submit" className="primary" disabled={patchSpec.isPending}>
                    Save
                  </Btn>
                  <Btn type="button" className="ghost" onClick={() => setAdding(false)}>
                    Cancel
                  </Btn>
                </div>
              </form>
            ) : (
              <Btn className="accent" onClick={() => setAdding(true)}>
                Add guardrail
              </Btn>
            )}
          </div>
        )}

        {tab === "yaml" && (
          <pre className="yaml-preview">{data.yaml}</pre>
        )}
      </div>

      <div className="profile-actions">
        {error ? <ErrorState error={error} /> : null}
        <Btn
          className="primary"
          disabled={Boolean(busy) || !canApprove}
          onClick={() => onAction("approve")}
          title={!canApprove ? "This specification is already approved" : "Approve this specification and replace older versions"}
        >
          {busy === "approve" ? "Approving…" : canApprove ? "Approve" : "Approved"}
        </Btn>
        <Btn
          className="accent"
          disabled={Boolean(busy) || !canActivate}
          onClick={() => onAction("activate")}
          title={
            isActive
              ? "This agent is already live"
              : !isApproved
                ? "Specification must be approved before activating"
                : "Activate this agent specification"
          }
        >
          {busy === "activate" ? "Activating…" : isActive ? "Activated" : "Activate"}
        </Btn>
        <Btn
          className="ghost"
          disabled={Boolean(busy) || !canDelete}
          onClick={() => onAction("delete")}
          title={
            !canDelete
              ? !isRedundant
                ? "Only redundant specifications can be deleted."
                : "Approved workflows with newer replacement versions are replaced automatically when the newer version is approved."
              : isApproved && hasNoNewer
                ? "Decommission and delete this obsolete approved specification"
                : "Delete redundant specification"
          }
        >
          {busy === "delete" ? "Deleting…" : "Delete"}
        </Btn>
      </div>
    </>
  );
}

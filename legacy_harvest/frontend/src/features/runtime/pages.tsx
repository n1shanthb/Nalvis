import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Btn, BtnLink, Chip, EmptyState, ErrorState, Loading, PageHead, Panel } from "../../components/ui";
import { api, type JsonObject } from "../../lib/api";
import type { ActivityEvent, AgentListItem, AgentReadiness, MonitorResponse } from "../../lib/api/contracts";
import { titleCase } from "../../lib/format";
import { useApiQuery } from "../../lib/query";
import { useActiveProjectId } from "../../hooks/use-active-project";
import { useAgents } from "../agents/hooks/agents.hooks";
import { AgentProfileModal } from "../projects/components/agent-profile-modal";
import { useProject } from "../projects/hooks/projects.hooks";

function copyText(value: string) {
  void navigator.clipboard.writeText(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function publicError(text: string): string {
  let cleaned = text.replace(/<[^<>]* object at 0x[0-9A-Fa-f]+>/gi, "").replace(/\s+/g, " ").trim();
  if (cleaned.includes("has no attribute 'connect'")) {
    return "GitHub MCP could not start. Restart the API, then open a new PR.";
  }
  return cleaned.slice(0, 240);
}

type AgentRun = {
  id: string;
  running: boolean;
  phase: string;
  subject: string;
  startedAt: string;
  link: string;
  comment: string;
  reason: string;
  error: string;
  system: string;
};

function isFixtureRun(run: AgentRun): boolean {
  return /\ba\/b#\d+/.test(run.subject) || /^PR a\/b#/.test(run.subject);
}

function phaseLabel(run: AgentRun): string {
  if (run.running) return "running";
  if (run.reason === "mention_gate") return "waiting for @mention";
  if (run.reason === "cicd_non_failure") return "ignored";
  return run.phase;
}

function groupRuns(events: ActivityEvent[], systems: string[]): AgentRun[] {
  const allowed = new Set(systems);
  const buckets = new Map<string, ActivityEvent[]>();
  const order: string[] = [];
  for (const event of events) {
    const delivery = asText(event.payload?.delivery_id) || event.id;
    if (!buckets.has(delivery)) {
      buckets.set(delivery, []);
      order.push(delivery);
    }
    buckets.get(delivery)!.push(event);
  }
  return order.map(id => {
    const items = buckets.get(id)!;
    const finished = items.find(item => {
      const phase = asText(item.payload?.phase);
      return phase === "responded" || phase === "skipped" || phase === "failed";
    });
    const latest = finished || items[0];
    const payload = latest.payload || {};
    const outcomes = asRecord(payload.outcomes);
    const github = asRecord(outcomes.github);
    const gmail = asRecord(outcomes.gmail);
    const jira = asRecord(outcomes.jira);
    const calendar = asRecord(outcomes.calendar);
    const links = Array.isArray(payload.links) ? payload.links.map(asText) : [];
    const phase = asText(payload.phase || latest.type);
    let system = asText(latest.connected_system_id);
    let subject = asText(payload.subject);
    let link = links[0] || "";
    let comment = "";
    if (github.owner && (!allowed.size || allowed.has("github"))) {
      system = "github";
      const kind = github.is_pull_request ? "PR" : "Issue";
      subject = `${kind} ${asText(github.owner)}/${asText(github.repo)}${github.number != null ? `#${asText(github.number)}` : ""}`;
      if (github.title) subject += ` — ${asText(github.title)}`;
      link = asText(github.comment_url) || link;
      comment = asText(github.comment);
    } else if ((gmail.subject || gmail.from) && (!allowed.size || allowed.has("gmail"))) {
      system = "gmail";
      subject = asText(gmail.subject) || subject;
      comment = asText(gmail.reply);
    } else if (jira.issue_key && (!allowed.size || allowed.has("jira"))) {
      system = "jira";
      subject = asText(jira.issue_key) + (jira.title ? ` — ${asText(jira.title)}` : "");
      comment = asText(jira.comment);
    } else if (calendar.title && (!allowed.size || allowed.has("calendar"))) {
      system = "calendar";
      subject = asText(calendar.title) + (calendar.start ? ` · ${asText(calendar.start)}` : "");
      link = asText(calendar.html_link) || link;
    }
    return {
      id,
      running: phase === "activated" || phase === "received",
      phase,
      subject,
      startedAt: items[items.length - 1]?.created_at || latest.created_at,
      link,
      comment: phase === "responded" ? comment : "",
      reason: asText(payload.reason),
      error: asText(payload.error),
      system,
    };
  });
}

function SetupPanel({ specId, projectId, runtimeBase }: { specId: string; projectId: string; runtimeBase: string }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const readiness = useApiQuery<AgentReadiness>(
    ["agent-readiness", specId],
    `/agents/${encodeURIComponent(specId)}/readiness`,
    { refetchInterval: 4000, staleTime: 0 },
  );
  const startTunnel = useMutation({
    mutationFn: () => api("/tunnel/start", { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["agent-readiness", specId] });
      client.invalidateQueries({ queryKey: ["tunnel"] });
      client.invalidateQueries({ queryKey: ["inbound-health"] });
    },
  });
  const startWatch = useMutation({
    mutationFn: () => api("/gmail/watch", { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["agent-readiness", specId] }),
  });
  const reconnect = useMutation({
    mutationFn: () => api("/inbound/reconnect?force_watch=true", { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["agent-readiness", specId] });
      client.invalidateQueries({ queryKey: ["inbound-health"] });
    },
  });
  const inboundHealth = useApiQuery<JsonObject>(["inbound-health"], "/inbound/health", { refetchInterval: 5000 });
  const repoBindings = useApiQuery<{ github_repos?: string[] }>(
    ["source-bindings", projectId],
    `/projects/${encodeURIComponent(projectId)}/source-bindings`,
    { enabled: Boolean(projectId) && Boolean(readiness.data?.github?.required) },
  );
  const [repoDraft, setRepoDraft] = useState("");
  const saveRepos = useMutation({
    mutationFn: (repos: string[]) =>
      api(`/projects/${encodeURIComponent(projectId)}/source-bindings/github-repos`, {
        method: "PUT",
        body: JSON.stringify({ repos }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["source-bindings", projectId] });
      client.invalidateQueries({ queryKey: ["agent-readiness", specId] });
      setRepoDraft("");
    },
  });

  if (readiness.isPending) return <Panel title="Connect webhooks"><Loading text="Checking systems…" /></Panel>;
  if (readiness.error) return <Panel title="Connect webhooks"><ErrorState error={readiness.error} /></Panel>;

  const data = readiness.data;
  const urls = data.tunnel.urls || {};
  const inbound = data.inbound_systems.length
    ? data.inbound_systems
    : (["github", "gmail", "jira"] as const).filter(id => data.systems.includes(id));
  const listening = Boolean(
    data.tunnel.running && inbound.every(system => urls[system]) && !data.tunnel.url_changed,
  );
  const hint = data.tunnel.url_changed
    ? "paste the new URL"
    : listening
      ? "listening"
      : "needs a public URL";

  return (
    <Panel
      title="Connect webhooks"
      hint={hint}
      action={<Btn className="ghost" onClick={() => navigate(`${runtimeBase}/${encodeURIComponent(specId)}`)}>Done</Btn>}
    >
      <ol className="setup-steps">
        <li>
          <strong>GitHub App</strong>
          <span className="muted">{data.github.required ? (data.github.app_installed ? "Installed" : "Not installed") : "Not used by this agent"}</span>
        </li>
        {data.github.required ? (
          <li>
            <strong>GitHub repos for this project</strong>
            <p className="muted">Webhooks from these owner/repo paths route to this project&apos;s agents only.</p>
            {repoBindings.data?.github_repos?.length ? (
              <ul className="repo-binding-list">
                {repoBindings.data.github_repos.map(repo => (
                  <li key={repo}>
                    <code>{repo}</code>
                    <Btn
                      className="ghost"
                      disabled={saveRepos.isPending}
                      onClick={() =>
                        saveRepos.mutate(
                          (repoBindings.data?.github_repos || []).filter(item => item !== repo),
                        )
                      }
                    >
                      Remove
                    </Btn>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="state warning">No repos assigned — add one or webhooks won&apos;t bind to this project.</p>
            )}
            <div className="toolbar">
              <input
                value={repoDraft}
                onChange={event => setRepoDraft(event.target.value)}
                placeholder="owner/repo e.g. n1shanthb/nalvis-landing"
              />
              <Btn
                className="ghost"
                disabled={saveRepos.isPending || !repoDraft.trim()}
                onClick={() => {
                  const next = [...(repoBindings.data?.github_repos || []), repoDraft.trim()];
                  saveRepos.mutate(next);
                }}
              >
                {saveRepos.isPending ? "Saving…" : "Add repo"}
              </Btn>
            </div>
            {saveRepos.error ? <p className="state error">{String((saveRepos.error as Error).message || saveRepos.error)}</p> : null}
          </li>
        ) : null}
        {data.gmail.required ? (
          <li>
            <strong>Gmail</strong>
            <span className="muted">
              {data.gmail.mailbox || "not connected"}
              {data.gmail.watch_active ? " · watch on" : " · watch off"}
            </span>
            {data.gmail.watch_error ? <p className="state error">{data.gmail.watch_error}</p> : null}
            {!data.gmail.watch_active ? (
              <>
                {startWatch.error ? <p className="state error">{String(startWatch.error.message || startWatch.error)}</p> : null}
                <Btn className="ghost" disabled={startWatch.isPending || !data.gmail.configured} onClick={() => startWatch.mutate()}>
                  {startWatch.isPending ? "Starting…" : "Start watch"}
                </Btn>
              </>
            ) : null}
          </li>
        ) : null}
        <li>
          <strong>Public URL</strong>
          <div className="toolbar">
            <Btn className="primary" disabled={startTunnel.isPending || data.tunnel.running || !data.tunnel.binary} onClick={() => startTunnel.mutate()}>
              {startTunnel.isPending ? "Starting…" : data.tunnel.running ? "Tunnel running" : "Start tunnel"}
            </Btn>
            <Btn className="ghost" disabled={reconnect.isPending} onClick={() => reconnect.mutate()}>
              {reconnect.isPending ? "Reconnecting…" : "Reconnect inbound"}
            </Btn>
            <Chip tone={data.tunnel.running ? "good" : "warning"}>{data.tunnel.running ? "running" : "stopped"}</Chip>
          </div>
          {inboundHealth.data ? (
            <p className="muted">
              GitHub: {String((inboundHealth.data as { github?: { fix?: string } }).github?.fix || "…")}
              {" · "}
              Gmail: {String((inboundHealth.data as { gmail?: { fix?: string } }).gmail?.fix || "…")}
              {" · "}
              jobs pending {Number((inboundHealth.data as { jobs?: { pending?: number } }).jobs?.pending || 0)}
            </p>
          ) : null}
        </li>
        <li>
          <strong>Paste public webhook URLs</strong>
          <p className="muted">GitHub App webhook · GCP Pub/Sub push (gmail) · Jira webhook</p>
          {inbound.map(system => (
            <label key={system} className="copy-row">
              <span>{system === "gmail" ? "gmail (Pub/Sub)" : system}</span>
              <input readOnly value={urls[system] || ""} placeholder="Start the tunnel first" />
              <Btn className="ghost" disabled={!urls[system]} onClick={() => copyText(urls[system])}>Copy</Btn>
            </label>
          ))}
          <div className="cta-row">
            <Btn
              className="ghost"
              disabled={!inbound.some(system => urls[system])}
              onClick={() => copyText(inbound.map(system => urls[system]).filter(Boolean).join("\n"))}
            >
              Copy all webhook URLs
            </Btn>
          </div>
        </li>
      </ol>
      {data.tunnel.url_changed ? (
        <p className="tunnel-alert">
          Tunnel URL changed — paste into GitHub App webhook + GCP Pub/Sub push endpoint (gmail). Click Reconnect inbound for History catch-up without waiting for Pub/Sub.
        </p>
      ) : null}
    </Panel>
  );
}

function RunRow({ run }: { run: AgentRun }) {
  const tone = run.running ? "accent" : run.phase === "failed" ? "bad" : run.phase === "skipped" ? "warning" : "good";
  const reason = run.reason === "mention_gate" || run.reason === "cicd_non_failure" ? "" : run.reason;
  return (
    <article className="run-row">
      <time dateTime={run.startedAt}>{new Date(run.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
      <Chip tone={tone}>{phaseLabel(run)}</Chip>
      <div className="run-row-body">
        {run.link ? (
          <a href={run.link} target="_blank" rel="noreferrer">{run.subject || "Open event"}</a>
        ) : (
          <span>{run.subject || "Event"}</span>
        )}
        {run.comment ? <p className="muted">{run.comment}</p> : null}
        {reason ? <p className="muted">{reason}</p> : null}
        {run.error ? <p className="state error">{publicError(run.error)}</p> : null}
      </div>
    </article>
  );
}

function isActivatedForProject(agent: AgentListItem, projectId: string): boolean {
  if (agent.approval_status !== "active") return false;
  if ((agent.project_id || "").trim() === projectId) return true;
  if ((agent.scope_level || "project") !== "company") return false;
  const origin = (agent.discovered_from || agent.org_id || "").trim();
  return origin === projectId;
}

function agentScopeLine(agent: AgentListItem, projectName: string): string {
  const parts = [`Project: ${projectName}`];
  if (agent.department) parts.push(titleCase(agent.department));
  if (agent.team_name) parts.push(agent.team_name);
  if (agent.role) parts.push(titleCase(agent.role));
  return parts.join(" · ");
}

export function RuntimePage() {
  const { specId, projectId: routeProjectId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const storedProjectId = useActiveProjectId();
  const projectId = routeProjectId || storedProjectId;
  const runtimeBase = projectId ? `/projects/${encodeURIComponent(projectId)}/runtime` : "/runtime";
  const [profileSpecId, setProfileSpecId] = useState<string | null>(null);
  const agents = useAgents(projectId);
  const project = useProject(projectId || "");
  const setupOpen = params.get("setup") === "1" && Boolean(specId);
  const monitor = useApiQuery<MonitorResponse>(
    ["monitor", specId || "", projectId || ""],
    `/monitor/events?spec_id=${encodeURIComponent(specId || "")}&limit=200`,
    { refetchInterval: 4000, staleTime: 0, enabled: Boolean(specId) },
  );

  if (!projectId) {
    return (
      <>
        <PageHead title="Runtime" subtitle="Activated agents are listed per project." />
        <Panel title="Activated agents">
          <EmptyState
            title="Open a project"
            description="Runtime only shows agents you activated for that project."
          />
          <BtnLink to="/" className="primary">Go to dashboard</BtnLink>
        </Panel>
      </>
    );
  }

  if (agents.isPending) return <Loading />;
  if (agents.error) return <ErrorState error={agents.error} />;
  if (specId && monitor.isPending) return <Loading />;
  if (specId && monitor.error) return <ErrorState error={monitor.error} />;

  const projectName = project.data?.project.name || projectId;
  const list = (agents.data?.agents ?? []).filter((agent: AgentListItem) => isActivatedForProject(agent, projectId));
  const selected = specId ? list.find((agent: AgentListItem) => agent.spec_id === specId) : undefined;
  const runs = groupRuns(monitor.data?.events || [], selected?.systems || []).filter(run => !isFixtureRun(run));

  return (
    <div className="runtime-layout">
      <PageHead
        title="Runtime"
        subtitle={`Activated agents for ${projectName}`}
        action={<BtnLink className="ghost" to={`/projects/${encodeURIComponent(projectId)}`}>Workspace</BtnLink>}
      />

      {list.length ? (
        <div className="runtime-workspace">
          <aside className="runtime-agent-rail" aria-label="Activated agents">
            <div className="runtime-agent-rail-head">
              <p className="surface-label">Agents</p>
              <Chip soft>{list.length}</Chip>
            </div>
            <nav className="runtime-agent-list">
              {list.map((agent: AgentListItem) => {
                const href = `${runtimeBase}/${encodeURIComponent(agent.spec_id)}`;
                const active = agent.spec_id === specId;
                return (
                  <button
                    key={agent.spec_id}
                    type="button"
                    className={`runtime-agent-item${active ? " active" : ""}`}
                    onClick={() => navigate(href)}
                  >
                    <span className="runtime-agent-title">{agent.title}</span>
                    <span className="runtime-agent-meta">
                      <Chip tone="good">Live</Chip>
                      {(agent.systems || []).slice(0, 2).map(system => (
                        <Chip key={system} soft>{system}</Chip>
                      ))}
                    </span>
                    <span className="muted runtime-agent-scope">{agentScopeLine(agent, projectName)}</span>
                  </button>
                );
              })}
            </nav>
          </aside>

          <div className="runtime-agent-main">
            {selected ? (
              <>
                <header className="runtime-agent-header">
                  <div>
                    <h2 className="runtime-agent-heading">{selected.title}</h2>
                    <p className="spec-card-id"><code>{selected.spec_id}</code></p>
                    <p className="muted">{selected.goal || agentScopeLine(selected, projectName)}</p>
                    <div className="tag-row" style={{ marginTop: "0.65rem" }}>
                      <Chip tone="good">Live</Chip>
                      {selected.scope_level === "company" ? <Chip soft>company</Chip> : null}
                      {(selected.systems || []).map(system => <Chip key={system} soft>{system}</Chip>)}
                      <Chip soft>{selected.tools.length} tools</Chip>
                    </div>
                  </div>
                  <div className="toolbar">
                    <Btn className="primary" onClick={() => setProfileSpecId(selected.spec_id)}>Open profile</Btn>
                    <BtnLink
                      className={setupOpen ? "primary" : "ghost"}
                      to={
                        setupOpen
                          ? `${runtimeBase}/${encodeURIComponent(selected.spec_id)}`
                          : `${runtimeBase}/${encodeURIComponent(selected.spec_id)}?setup=1`
                      }
                    >
                      {setupOpen ? "Hide connect" : "Connect"}
                    </BtnLink>
                  </div>
                </header>

                {setupOpen ? <SetupPanel specId={selected.spec_id} projectId={projectId} runtimeBase={runtimeBase} /> : null}

                <Panel title="Activity" hint={runs.length ? `${runs.length}` : undefined}>
                  {runs.length ? runs.map(run => <RunRow key={run.id} run={run} />) : (
                    <EmptyState
                      title="Waiting for an event"
                      description="Connect webhooks, then open a PR or send mail."
                    />
                  )}
                </Panel>
              </>
            ) : (
              <Panel title="Select an agent">
                <EmptyState
                  title="Choose an agent"
                  description="Pick an activated agent from the sidebar to view connect status and runtime activity."
                />
              </Panel>
            )}
          </div>
        </div>
      ) : (
        <Panel title="Activated agents">
          <EmptyState
            title="No activated agents"
            description="Approve and activate a spec in this project's workspace. Drafts and agents from other projects stay off this list."
          />
        </Panel>
      )}

      {profileSpecId ? (
        <AgentProfileModal
          projectId={projectId}
          specId={profileSpecId}
          onClose={() => setProfileSpecId(null)}
        />
      ) : null}
    </div>
  );
}

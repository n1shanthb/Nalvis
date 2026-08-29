import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Btn, Chip, ErrorState, Loading, PageHead, Panel, StatRow } from "../components/ui";
import { api, type JsonObject } from "../lib/api";
import { useApiQuery } from "../lib/query";

function ConfigurationForm({ system, onSaved }: { system: JsonObject; onSaved: () => void }) {
  const [value, setValue] = useState(system);
  const save = useMutation({
    mutationFn: () => api(`/mcps/${system.id}`, { method: "PATCH", body: JSON.stringify(value) }),
    onSuccess: onSaved,
  });

  return (
    <form className="form-stack" onSubmit={e => { e.preventDefault(); save.mutate(); }}>
      <label>Display name<input value={value.display_name} onChange={e => setValue({ ...value, display_name: e.target.value })} /></label>
      <label>MCP URL<input value={value.mcp_url || ""} onChange={e => setValue({ ...value, mcp_url: e.target.value })} /></label>
      <label>Toolsets<input value={value.toolsets || ""} onChange={e => setValue({ ...value, toolsets: e.target.value })} /></label>
      <label>Description<textarea rows={3} value={value.description || ""} onChange={e => setValue({ ...value, description: e.target.value })} /></label>
      <Btn className="primary" type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</Btn>
    </form>
  );
}

function copyText(value: string) {
  void navigator.clipboard.writeText(value);
}

function TunnelPanel() {
  const client = useQueryClient();
  const tunnel = useApiQuery<JsonObject>(["tunnel"], "/tunnel", { refetchInterval: 2500 });
  const health = useApiQuery<JsonObject>(["inbound-health"], "/inbound/health", { refetchInterval: 5000 });
  const start = useMutation({
    mutationFn: () => api("/tunnel/start", { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["tunnel"] });
      client.invalidateQueries({ queryKey: ["inbound-health"] });
    },
  });
  const stop = useMutation({
    mutationFn: () => api("/tunnel/stop", { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["tunnel"] });
      client.invalidateQueries({ queryKey: ["inbound-health"] });
    },
  });
  const reconnect = useMutation({
    mutationFn: () => api("/inbound/reconnect?force_watch=true", { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["inbound-health"] }),
  });

  if (tunnel.isPending) return <Panel title="Public webhook tunnel"><Loading text="Checking tunnel…" /></Panel>;
  if (tunnel.error) return <Panel title="Public webhook tunnel"><ErrorState error={tunnel.error} /></Panel>;
  const data = tunnel.data;
  const urls = (data.urls || {}) as Record<string, string>;
  const running = Boolean(data.running);
  const busy = start.isPending || stop.isPending || reconnect.isPending;
  const h = health.data || {};
  const jobs = (h.jobs || {}) as Record<string, number>;

  return (
    <Panel title="Public webhook tunnel" hint={String(data.status || "stopped")}>
      {data.url_changed ? (
        <p className="tunnel-alert">
          Tunnel URL changed — paste the new GitHub App webhook URL and the Gmail GCP Pub/Sub <strong>push endpoint</strong>. History catch-up still runs without Pub/Sub.
        </p>
      ) : null}
      {!data.binary ? <p className="muted">{String(data.install_hint || "")}</p> : null}
      {data.error ? <p className="muted">{String(data.error)}</p> : null}
      <div className="toolbar">
        <Btn className="primary" disabled={busy || running || !data.binary} onClick={() => start.mutate()}>
          {start.isPending ? "Starting…" : "Start Cloudflare tunnel"}
        </Btn>
        <Btn className="ghost" disabled={busy || !running} onClick={() => stop.mutate()}>
          {stop.isPending ? "Stopping…" : "Stop"}
        </Btn>
        <Btn className="ghost" disabled={busy} onClick={() => reconnect.mutate()}>
          {reconnect.isPending ? "Reconnecting…" : "Reconnect inbound"}
        </Btn>
        <Chip tone={running ? "good" : "warning"}>{running ? "running" : String(data.status || "stopped")}</Chip>
      </div>
      <div className="toolbar" style={{ marginTop: "0.5rem" }}>
        <Chip tone={(h.github as { tone?: string } | undefined)?.tone === "good" ? "good" : "warning"}>
          GitHub: {String((h.github as { fix?: string } | undefined)?.fix || "…")}
        </Chip>
        <Chip
          tone={
            (h.gmail as { tone?: string } | undefined)?.tone === "good"
              ? "good"
              : (h.gmail as { tone?: string } | undefined)?.tone === "bad"
                ? "bad"
                : "warning"
          }
        >
          Gmail: {String((h.gmail as { fix?: string } | undefined)?.fix || "…")}
        </Chip>
        <Chip
          tone={
            (h.jobs_tone as string | undefined) === "bad"
              ? "bad"
              : (h.jobs_tone as string | undefined) === "warning"
                ? "warning"
                : "good"
          }
        >
          Jobs p{Number(jobs.pending || 0)}/d{Number(jobs.dead || 0)}
        </Chip>
      </div>
      {(["github", "jira", "gmail"] as const).map(system => (
        <label key={system} className="copy-row">
          <span>{system === "gmail" ? "gmail (Pub/Sub push)" : system}</span>
          <input readOnly value={urls[system] || ""} placeholder="Start the tunnel to get a public URL" />
          <Btn className="ghost" disabled={!urls[system]} onClick={() => copyText(urls[system])}>Copy</Btn>
        </label>
      ))}
      <div className="cta-row">
        <Btn
          className="ghost"
          disabled={!Object.values(urls).some(Boolean)}
          onClick={() => copyText(["github", "jira", "gmail"].map(s => urls[s]).filter(Boolean).join("\n"))}
        >
          Copy all webhook URLs
        </Btn>
      </div>
    </Panel>
  );
}

export default function McpDetailPage() {
  const { systemId = "" } = useParams();
  const client = useQueryClient();
  const mcp = useApiQuery(["mcp", systemId], `/mcps/${systemId}`);
  const action = useMutation({
    mutationFn: (actionName: string) => api(`/mcps/${systemId}/${actionName}`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["mcp", systemId] }),
  });

  if (mcp.isPending) return <Loading />;
  if (mcp.error) return <ErrorState error={mcp.error} />;
  const system = mcp.data.system;
  const highlight = new Set([
    "pull_request.opened",
    "pull_request.synchronize",
    "pull_request.reopened",
    "issues.opened",
    "issue_comment.created",
    "workflow_run.completed",
  ]);
  const inventory = system.id === "github"
    ? (system.webhooks || []).filter((webhook: JsonObject) => highlight.has(String(webhook.id)))
    : system.webhooks || [];

  return (
    <>
      <Link className="back-link" to="/mcps">← Systems</Link>
      <PageHead title={system.display_name} subtitle={system.description || "Connected system configuration"} />
      <StatRow items={[[system.status, "Status"], [system.health, "Health"], [system.tool_count, "Tools"]]} />

      <div className="toolbar">
        <Btn className="primary" onClick={() => action.mutate("connect")} disabled={action.isPending}>Connect</Btn>
        <Btn onClick={() => action.mutate("discover")} disabled={action.isPending}>Discover tools</Btn>
        {["github", "jira", "gmail"].includes(system.id) && (
          <Btn className="ghost" onClick={() => action.mutate("seed-webhooks")} disabled={action.isPending}>Seed webhooks</Btn>
        )}
      </div>

      {["github", "jira", "gmail"].includes(system.id) ? <TunnelPanel /> : null}

      <Panel title="Discovered tools" hint={`${system.tools.length} tools`}>
        <ul className="tool-index">
          {system.tools.map((tool: JsonObject) => (
            <li key={tool.name}>
              <code>{tool.name}</code>
              <span className="muted">{tool.toolset}</span>
              <p>{tool.description}</p>
            </li>
          ))}
        </ul>
      </Panel>

      {inventory.length > 0 && (
        <Panel title="Webhook inventory">
          <ul className="list-plain">
            {inventory.map((webhook: JsonObject) => (
              <li key={webhook.id}>
                <strong>{webhook.id}</strong>
                <span className="muted"> · {webhook.event}{webhook.action ? `.${webhook.action}` : ""}</span>
                <p className="muted">{webhook.description}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {system.bindings?.length > 0 && (
        <Panel title="Listening agents" hint="Activated specs bound to these events">
          <ul className="list-plain">
            {system.bindings.map((binding: JsonObject) => (
              <li key={`${binding.webhook_id}:${binding.spec_id}`}>
                <code>{binding.webhook_id}</code>
                <span className="muted"> → {binding.spec_id}{binding.enabled ? "" : " (disabled)"}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel title="Configuration">
        <ConfigurationForm system={system} onSaved={() => client.invalidateQueries({ queryKey: ["mcp", systemId] })} />
      </Panel>
    </>
  );
}

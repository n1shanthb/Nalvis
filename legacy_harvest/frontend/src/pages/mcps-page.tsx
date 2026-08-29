import { Link } from "react-router-dom";
import { Chip, ErrorState, Loading, PageHead, StatRow } from "../components/ui";
import type { McpSystem } from "../lib/api/contracts";
import { useApiQuery } from "../lib/query";

const SYSTEM_META: Record<string, { mark: string; color: string }> = {
  github: { mark: "GH", color: "#24292f" },
  gmail: { mark: "GM", color: "#ea4335" },
  google_calendar: { mark: "GC", color: "#4285f4" },
  jira: { mark: "JR", color: "#0052cc" },
};

function SystemCard({ system }: { system: McpSystem }) {
  const meta = SYSTEM_META[system.id] ?? { mark: system.display_name.slice(0, 2).toUpperCase(), color: "#5B5D62" };
  const connected = system.status === "connected";
  const healthy = system.health === "healthy";

  return (
    <Link className="system-card" to={`/mcps/${system.id}`}>
      <span className="system-icon" style={{ background: meta.color }} aria-hidden="true">
        {meta.mark}
      </span>
      <div className="system-body">
        <h3>{system.display_name}</h3>
        <p className="system-desc">{system.description || "Connected system integration"}</p>
        <div className="system-meta">
          <Chip tone={connected ? "good" : "warning"}>{system.status}</Chip>
          {healthy && <Chip soft>healthy</Chip>}
          <span className="muted">{system.tool_count} tools</span>
          <span className="muted">{system.configured ? "configured" : "needs setup"}</span>
        </div>
      </div>
      <span className="system-arrow" aria-hidden="true">→</span>
    </Link>
  );
}

export default function McpsPage() {
  const mcps = useApiQuery(["mcps"], "/mcps");

  if (mcps.isPending) return <Loading />;
  if (mcps.error) return <ErrorState error={mcps.error} />;
  const data = mcps.data;

  return (
    <>
      <PageHead
        title="Connected systems"
        subtitle="GitHub, Gmail, Google Calendar, and Jira — connect once, use everywhere."
      />
      <StatRow
        items={[
          [data.summary.total, "Registered"],
          [data.summary.connected, "Connected"],
          [data.summary.configured, "Configured"],
        ]}
      />
      <div className="system-grid">
        {data.systems.map((system: McpSystem) => (
          <SystemCard key={system.id} system={system} />
        ))}
      </div>
    </>
  );
}

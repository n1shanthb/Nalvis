import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Btn, Chip, EmptyState, ErrorState, Loading, PageHead, Panel } from "../../components/ui";
import type { AgentListItem, Tool } from "../../lib/api/contracts";
import { QueryBoundary } from "../../lib/query";
import { useAgent, useAgents, useAssignTools } from "./hooks/agents.hooks";

export function AgentsPage() {
  const agents = useAgents();
  if (agents.isPending) return <Loading />;
  if (agents.error) return <ErrorState error={agents.error} />;
  const data = agents.data;

  return (
    <>
      <PageHead title="Agents" subtitle="Active specifications and their tool assignments." />
      <Panel title="Active specs" hint={`${data.agents.length} agents`}>
        {data.agents.length ? (
          <div className="agent-grid">
            {data.agents.map((agent: AgentListItem) => (
              <Link key={agent.spec_id} className="agent-card" to={`/agents/${agent.spec_id}`}>
                <h3>{agent.title}</h3>
                <p className="muted truncate-id" title={agent.spec_id}>
                  <code>{agent.spec_id}</code>
                </p>
                <div className="tag-row">
                  <Chip soft>{agent.tools.length} tools</Chip>
                  {agent.systems?.map(s => <Chip key={s}>{s}</Chip>)}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState title="No agents yet" description="Run discovery and activate a spec." />
        )}
      </Panel>
    </>
  );
}

export function AgentDetailPage() {
  const { specId = "" } = useParams();
  const agent = useAgent(specId);
  const assign = useAssignTools(specId);
  const [selected, setSelected] = useState<string[] | null>(null);

  if (agent.isPending) return <Loading />;
  if (agent.error) return <ErrorState error={agent.error} />;
  const data = agent.data;
  const chosen = selected ?? data.assigned_keys;

  return (
    <>
      <Link className="back-link" to="/agents">← Agents</Link>
      <PageHead
        title={data.spec.agent.title}
        subtitle={data.spec.goal}
        action={<Link className="btn ghost" to={`/runtime/${encodeURIComponent(specId)}`}>Runtime</Link>}
      />
      <Panel title="Tool marketplace">
        <p className="lead">Assign discovered tools. Credentials stay on the server.</p>
        {Object.entries(data.marketplace).map(([system, tools]) => (
          <div key={system} className="marketplace-group">
            <p className="surface-label">{system}</p>
            {tools.length ? (
              <ul className="check-list">
                {(tools as Tool[]).map(tool => {
                  const key = `${system}::${tool.name}`;
                  return (
                    <li key={key}>
                      <label className="check-row">
                        <input
                          type="checkbox"
                          checked={chosen.includes(key)}
                          onChange={e => setSelected(e.target.checked ? [...chosen, key] : chosen.filter(item => item !== key))}
                        />
                        <span>
                          <code>{tool.name}</code>
                          <small className="muted">{tool.description}</small>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted">No tools discovered.</p>
            )}
          </div>
        ))}
        <Btn className="primary" onClick={() => assign.mutate(chosen)} disabled={assign.isPending}>
          {assign.isPending ? "Saving…" : "Save assignment"}
        </Btn>
      </Panel>
    </>
  );
}

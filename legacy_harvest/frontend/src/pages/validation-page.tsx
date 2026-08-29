import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Btn, Chip, EmptyState, ErrorState, Loading, PageHead, Panel, StatRow } from "../components/ui";
import { useAgents } from "../features/agents/hooks/agents.hooks";
import { useActiveProjectId } from "../hooks/use-active-project";
import { api } from "../lib/api";
import type { ValidationRecordDto } from "../lib/api/contracts";
import { useApiQuery } from "../lib/query";

type Verdict = "PASS" | "FAIL" | "PARTIAL" | "REVIEW";
type ExecutionRow = {
  execution_id: string;
  agent_id: string;
  project_id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  failure_reason?: string;
  waiting_for_approval_id?: string | null;
};

const VALIDATION_STEPS = ["Claim verification", "Response SLA", "Guardrail bypass", "Final verdict"] as const;

export default function ValidationPage() {
  const projectId = useActiveProjectId();
  const queryClient = useQueryClient();
  const executionsQuery = useApiQuery<{ executions?: ExecutionRow[] }>(["executions"], "/executions");
  const validationsQuery = useApiQuery<{ validations?: ValidationRecordDto[] }>(
    ["validations", projectId],
    `/validations?project_id=${encodeURIComponent(projectId || "")}`,
    { enabled: Boolean(projectId),
    },
  );
  const agents = useAgents();
  const monitor = useApiQuery<{ events?: import("../lib/api").JsonObject[] }>(["monitor"], "/monitor/events");
  const [search, setSearch] = useState("");
  const [range, setRange] = useState("all");
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);

  const titles = useMemo(() => {
    const map = new Map<string, string>();
    for (const agent of agents.data?.agents ?? []) map.set(agent.spec_id, agent.title);
    return map;
  }, [agents.data]);

  const liveExecutions = useMemo(
    () => (executionsQuery.data?.executions ?? []).filter(row => row.project_id === projectId),
    [executionsQuery.data, projectId],
  );

  const realValidations = validationsQuery.data?.validations ?? [];
  const execById = useMemo(() => new Map(liveExecutions.map(row => [row.execution_id, row])), [liveExecutions]);

  const rows = useMemo(() => {
    if (!projectId) return [];
    const cutoff = rangeCutoff(range);
    const q = search.trim().toLowerCase();

    if (realValidations.length) {
      return realValidations
        .filter(v => !cutoff || (v.created_at && new Date(v.created_at).getTime() >= cutoff))
        .map(v => {
          const row = v.execution_id ? execById.get(v.execution_id) : undefined;
          const agent = titles.get(v.spec_id) || v.spec_id;
          const synthetic: ExecutionRow = row || {
            execution_id: v.execution_id || v.watch_id || v.spec_id,
            agent_id: v.spec_id,
            project_id: v.project_id,
            status: v.verdict === "FAIL" ? "FAILED" : "COMPLETED",
            created_at: v.created_at || new Date().toISOString(),
            completed_at: v.created_at,
          };
          return {
            row: synthetic,
            result: validationToUi(v),
            agent,
            validation: v,
          };
        })
        .filter(({ row, result, agent }) => {
          if (verdictFilter !== "all" && result.verdict !== verdictFilter) return false;
          if (!q) return true;
          return `${row.execution_id} ${row.agent_id} ${agent} ${result.verdict}`.toLowerCase().includes(q);
        });
    }

    return liveExecutions
      .filter(row => !cutoff || new Date(row.created_at).getTime() >= cutoff)
      .map(row => {
        const agent = titles.get(row.agent_id) || row.agent_id;
        return {
          row,
          result: {
            verdict: row.status === "FAILED" ? "FAIL" as Verdict : "PASS" as Verdict,
            confidence: 0,
            durationMs: 0,
            dimensions: {},
            violations: row.failure_reason ? [row.failure_reason] : [],
            evidence: { claim: "", interpretation: "" },
            outcome: { reported: row.status, expected: "", observed: row.failure_reason || row.status },
          },
          agent,
          validation: null as ValidationRecordDto | null,
        };
      })
      .filter(({ row, agent }) => {
        if (verdictFilter !== "all") return false;
        if (!q) return true;
        return `${row.execution_id} ${row.agent_id} ${agent} ${row.status}`.toLowerCase().includes(q);
      });
  }, [execById, liveExecutions, projectId, range, realValidations, search, titles, verdictFilter]);

  if (!projectId) {
    return (
      <>
        <PageHead title="Validation" subtitle="Independent verification of agent executions" />
        <EmptyState title="No workspace selected" description="Open a project from the Dashboard to inspect its executions." />
        <p><Link className="btn" to="/">Go to Dashboard</Link></p>
      </>
    );
  }

  if (executionsQuery.isPending || validationsQuery.isPending) return <Loading />;
  if (executionsQuery.error) return <ErrorState error={executionsQuery.error} />;
  if (validationsQuery.error) return <ErrorState error={validationsQuery.error} />;

  const selected = rows.find(item => item.row.execution_id === selectedId);
  const passed = rows.filter(item => item.result.verdict === "PASS").length;
  const flagged = rows.filter(item => item.result.verdict === "PARTIAL" || item.result.verdict === "REVIEW").length;
  const critical = rows.filter(item => item.result.verdict === "FAIL").length;
  const avgMs = rows.length ? Math.round(rows.reduce((sum, item) => sum + item.result.durationMs, 0) / rows.length) : 0;

  const liveEvents = selected
    ? (monitor.data?.events ?? []).filter(event => {
        if (String(event.spec_id || "") !== selected.row.agent_id) return false;
        const at = new Date(String(event.created_at)).getTime();
        const start = new Date(selected.row.created_at).getTime() - 60_000;
        const end = new Date(selected.row.completed_at || selected.row.created_at).getTime() + 5 * 60_000;
        return at >= start && at <= end;
      })
    : [];

  function rerun() {
    if (!selectedId || !selected?.validation?.execution_id) return;
    setRerunning(true);
    void api(`/executions/${encodeURIComponent(selected.validation.execution_id!)}/validation/revalidate`, { method: "POST" })
      .then(() => queryClient.invalidateQueries({ queryKey: ["validations", projectId] }))
      .finally(() => setRerunning(false));
  }

  return (
    <>
      <PageHead eyebrow={projectId} title="Validation" subtitle="Independent verification of agent executions" />
      <div className="toolbar">
        <input className="tool-filter" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search executions" />
        <select className="tool-filter" value={range} onChange={e => setRange(e.target.value)} aria-label="Time range">
          <option value="all">All time</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
        </select>
        <select className="tool-filter" value={verdictFilter} onChange={e => setVerdictFilter(e.target.value)} aria-label="Verdict">
          <option value="all">All verdicts</option>
          <option value="PASS">PASS</option>
          <option value="PARTIAL">PARTIAL</option>
          <option value="FAIL">FAIL</option>
          <option value="REVIEW">REVIEW</option>
        </select>
      </div>
      <StatRow
        items={[
          [rows.length, "Executions"],
          [realValidations.length, "Validated"],
          [passed, "Passed"],
          [flagged, "Flagged"],
          [critical, "Critical"],
          [rows.length ? `${avgMs} ms` : "—", "Avg validation time"],
        ]}
      />
      <Panel title="Executions" hint={`${rows.length} in ${projectId}`}>
        {rows.length ? (
          <div className="validation-table-wrap">
            <table className="validation-table">
              <thead>
                <tr>
                  <th>Execution</th>
                  <th>Agent</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>Verdict</th>
                  <th>Confidence</th>
                  <th>Issues</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ row, result, agent }) => (
                  <tr key={row.execution_id} onClick={() => setSelectedId(row.execution_id)}>
                    <td><code>{row.execution_id}</code></td>
                    <td>{agent}</td>
                    <td>{formatWhen(row.created_at)}</td>
                    <td>{formatDuration(row.created_at, row.completed_at)}</td>
                    <td><VerdictChip value={result.verdict} /></td>
                    <td>{result.confidence ? `${Math.round(result.confidence <= 1 ? result.confidence * 100 : result.confidence)}%` : "—"}</td>
                    <td>{result.violations.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No executions in this workspace" description="Run an agent or wait for inbound events to produce validation records." />
        )}
      </Panel>

      {selected && (
        <div className="profile-overlay validation-drawer" onClick={() => setSelectedId(null)}>
          <div className="profile-modal" onClick={e => e.stopPropagation()}>
            <div className="surface-header">
              <h2 className="surface-title">Validation detail</h2>
              <button className="profile-close" type="button" onClick={() => setSelectedId(null)} aria-label="Close">Close</button>
            </div>
            <p className="muted"><code>{selected.row.execution_id}</code></p>

            <div className="validation-summary">
              <div><p className="surface-label">Verdict</p><VerdictChip value={selected.result.verdict} /></div>
              <div><p className="surface-label">Confidence</p><p>{selected.result.confidence ? `${Math.round(selected.result.confidence * (selected.result.confidence <= 1 ? 100 : 1))}%` : "—"}</p></div>
              {selected.validation ? (
                <>
                  <div><p className="surface-label">Outcome</p><Chip tone={markTone(selected.validation.check_marks?.outcome || "NOT_APPLICABLE")}>{selected.validation.check_marks?.outcome || "NOT_APPLICABLE"}</Chip></div>
                  <div><p className="surface-label">Response SLA</p><Chip tone={markTone(selected.validation.check_marks?.response_sla || "NOT_APPLICABLE")}>{selected.validation.check_marks?.response_sla || "NOT_APPLICABLE"}</Chip></div>
                  <div><p className="surface-label">Guardrail bypass</p><Chip tone={markTone(selected.validation.check_marks?.guardrail_bypass || "NOT_APPLICABLE")}>{selected.validation.check_marks?.guardrail_bypass || "NOT_APPLICABLE"}</Chip></div>
                </>
              ) : null}
              <div><p className="surface-label">Agent</p><p>{selected.agent}</p></div>
            </div>
            {selected.validation?.objective ? <p className="muted"><strong>Objective:</strong> {selected.validation.objective}</p> : null}
            {selected.validation?.claimed_action ? <p className="muted"><strong>Claimed action:</strong> {selected.validation.claimed_action}</p> : null}

            {selected.validation ? (
              <>
                <h3 className="validation-section">Check marks</h3>
                <div className="validation-scorecard">
                  <div><span>Outcome</span><Chip tone={markTone(selected.validation.check_marks?.outcome || "NOT_APPLICABLE")}>{selected.validation.check_marks?.outcome || "NOT_APPLICABLE"}</Chip></div>
                  <div><span>Response SLA</span><Chip tone={markTone(selected.validation.check_marks?.response_sla || "NOT_APPLICABLE")}>{selected.validation.check_marks?.response_sla || "NOT_APPLICABLE"}</Chip></div>
                  <div><span>Guardrail bypass</span><Chip tone={markTone(selected.validation.check_marks?.guardrail_bypass || "NOT_APPLICABLE")}>{selected.validation.check_marks?.guardrail_bypass || "NOT_APPLICABLE"}</Chip></div>
                  <div><span>Log</span><Chip tone={markTone(selected.validation.check_marks?.log_ok || "PASS")}>{selected.validation.check_marks?.log_ok || "PASS"}</Chip></div>
                </div>
              </>
            ) : null}

            <h3 className="validation-section">Timeline</h3>
            <div className="console">
              {liveEvents.length ? liveEvents.map(event => (
                <div key={String(event.id)}>
                  <time>{new Date(String(event.created_at)).toLocaleTimeString()}</time>
                  <Chip soft>{String(event.payload?.phase || event.type)}</Chip>
                  <b>{String(event.employee || event.spec_id || "agent")}</b>
                  <span>{String(event.payload?.subject || event.message)}</span>
                </div>
              )) : (
                <div><span className="muted">No monitor events for this execution window.</span></div>
              )}
              {selected.validation ? VALIDATION_STEPS.map(step => (
                <div key={step} className="validation-event">
                  <time>val</time>
                  <Chip tone="accent">{step}</Chip>
                  <b>Validation</b>
                  <span>{selected.result.verdict}</span>
                </div>
              )) : null}
            </div>

            <h3 className="validation-section">Evidence</h3>
            <div className="validation-block">
              <p><span className="surface-label">Agent claim</span> {selected.result.evidence.claim || selected.validation?.claimed_action || "—"}</p>
              <p><span className="surface-label">Expected</span> {selected.result.outcome.expected || selected.validation?.expected || "—"}</p>
              <p><span className="surface-label">Observed</span> {selected.result.outcome.observed || selected.validation?.observed || "—"}</p>
              <p><span className="surface-label">Reference</span> <code>{selected.row.agent_id}</code></p>
            </div>

            <h3 className="validation-section">Violations</h3>
            {selected.result.violations.length ? (
              <ul className="list-plain">
                {selected.result.violations.map(item => <li key={item}>{item}</li>)}
              </ul>
            ) : (
              <p className="muted">No validation findings on this execution.</p>
            )}

            {selected.validation?.execution_id ? (
              <div className="cta-row" style={{ marginTop: "1.25rem" }}>
                <Btn className="accent" disabled={rerunning} onClick={rerun}>{rerunning ? "Validating…" : "Re-run validation"}</Btn>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}

function VerdictChip({ value }: { value: Verdict }) {
  return <Chip tone={chipTone(value)}>{value}</Chip>;
}

function markTone(status: string): "good" | "bad" | "accent" | "warning" | "" {
  if (status === "PASS") return "good";
  if (status === "FAIL") return "bad";
  if (status === "PARTIAL") return "accent";
  if (status === "REVIEW" || status === "INSUFFICIENT_EVIDENCE") return "warning";
  return "";
}

function validationToUi(v: ValidationRecordDto) {
  const marks = v.check_marks || { outcome: "NOT_APPLICABLE", response_sla: "NOT_APPLICABLE", guardrail_bypass: "NOT_APPLICABLE", log_ok: "PASS" };
  const outcome = (marks.outcome || "NOT_APPLICABLE") as Verdict;
  return {
    verdict: (v.verdict || outcome) as Verdict,
    confidence: v.confidence ?? 0,
    durationMs: 0,
    dimensions: {
      Outcome: outcome,
      Temporal: (marks.response_sla || "NOT_APPLICABLE") as Verdict,
    },
    violations: v.verdict === "FAIL" ? [v.message || "Validation failed"].filter(Boolean) : [],
    evidence: { claim: v.claimed_action || v.expected, interpretation: v.observed },
    outcome: { reported: v.claimed_action, expected: v.expected, observed: v.observed },
  };
}

function chipTone(value: Verdict): "good" | "bad" | "accent" | "warning" {
  if (value === "PASS") return "good";
  if (value === "FAIL") return "bad";
  if (value === "PARTIAL") return "accent";
  return "warning";
}

function rangeCutoff(range: string) {
  const now = Date.now();
  if (range === "24h") return now - 24 * 60 * 60 * 1000;
  if (range === "7d") return now - 7 * 24 * 60 * 60 * 1000;
  if (range === "30d") return now - 30 * 24 * 60 * 60 * 1000;
  return 0;
}

function formatWhen(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function formatDuration(start: string, end?: string | null) {
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(from) || Number.isNaN(to) || to < from) return "—";
  const ms = to - from;
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${Math.round(ms / 1000)} s`;
  return `${Math.round(ms / 60_000)} min`;
}

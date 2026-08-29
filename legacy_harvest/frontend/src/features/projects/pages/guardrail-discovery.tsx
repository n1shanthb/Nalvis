import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../lib/api";
import { Btn, Panel } from "../../../components/ui";

type CandidateStatus = "DISCOVERED" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "ALREADY_PROTECTED";

interface GuardrailCandidate {
  id: string;
  project_id: string;
  agent_id: string;
  tool_name: string;
  target_system: string;
  scope: string;
  effect: string;
  risk_level: string;
  confidence: string;
  reason: string;
  status: CandidateStatus;
  tool_metadata?: {
    description: string;
    toolset?: string;
    capability_tags?: string[];
    permissions?: string[];
  };
}

export function GuardrailDiscoverySection({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["guardrailDiscovery", projectId],
    queryFn: () => api<{ ok: boolean; candidates: GuardrailCandidate[] }>(`/projects/${projectId}/guardrails/discovery`),
  });

  const runDiscoveryMutation = useMutation({
    mutationFn: () => api(`/projects/${projectId}/guardrails/discovery/run`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guardrailDiscovery", projectId] }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => api(`/guardrail-candidates/${id}/approve`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guardrailDiscovery", projectId] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api(`/guardrail-candidates/${id}/reject`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guardrailDiscovery", projectId] }),
  });

  if (isLoading) return <div>Loading discovery...</div>;

  const candidates = data?.candidates || [];
  const pending = candidates.filter(c => c.status === "DISCOVERED" || c.status === "PENDING_REVIEW");
  
  if (candidates.length === 0) {
    return (
      <div className="bg-neutral-900 rounded border border-neutral-800 mb-8 p-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">Guardrail Discovery</h2>
          <p className="text-sm text-neutral-400">No discovered recommendations yet. Run discovery to analyze agents.</p>
        </div>
        <Btn className="primary" onClick={() => runDiscoveryMutation.mutate()} disabled={runDiscoveryMutation.isPending}>
          {runDiscoveryMutation.isPending ? "Running..." : "Run Discovery"}
        </Btn>
      </div>
    );
  }

  const highConfidence = pending.filter(c => c.confidence === "HIGH").length;
  const displayList = showAll ? candidates : pending;

  return (
    <div className="bg-neutral-900 rounded border border-neutral-800 mb-8">
      <div className="p-6 border-b border-neutral-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">Guardrail Discovery</h2>
          <p className="text-sm text-neutral-400">
            {pending.length} recommendations ({highConfidence} High Confidence)
          </p>
        </div>
        <div className="form-inline">
          <Btn className="ghost" onClick={() => setShowAll(!showAll)}>
            {showAll ? "Show Pending Only" : "Show All"}
          </Btn>
          <Btn className="primary" onClick={() => runDiscoveryMutation.mutate()} disabled={runDiscoveryMutation.isPending}>
            {runDiscoveryMutation.isPending ? "Running..." : "Run Again"}
          </Btn>
        </div>
      </div>
      
      {displayList.length === 0 && (
         <div className="p-6 text-center text-sm text-neutral-500">No pending recommendations.</div>
      )}

      <div className="divide-y divide-neutral-800">
        {displayList.map(c => (
          <div key={c.id} className="p-6 flex flex-col gap-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-semibold text-white">Require {c.effect} for {c.tool_name}</h3>
                <div className="text-sm text-neutral-400 mt-1 flex items-center gap-3">
                  <span>Agent: <span className="text-neutral-300">{c.agent_id}</span></span>
                  <span>System: <span className="text-neutral-300">{c.target_system}</span></span>
                  <span>Scope: <span className="text-neutral-300">{c.scope}</span></span>
                </div>
              </div>
              <div className="flex gap-2">
                <span className={`px-2 py-1 text-xs rounded font-medium ${c.risk_level === 'CRITICAL' || c.risk_level === 'HIGH' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
                  Risk: {c.risk_level}
                </span>
                <span className={`px-2 py-1 text-xs rounded font-medium ${c.confidence === 'HIGH' ? 'bg-green-500/10 text-green-400' : 'bg-blue-500/10 text-blue-400'}`}>
                  Confidence: {c.confidence}
                </span>
              </div>
            </div>
            
            <div className="bg-neutral-900/50 p-4 rounded text-sm text-neutral-300 border border-neutral-800">
              <p>{c.reason}</p>
              {c.tool_metadata && (
                <div className="mt-3 pt-3 border-t border-neutral-800/50 flex flex-col gap-2 text-xs">
                  {c.tool_metadata.description && (
                    <p className="text-neutral-400"><span className="font-medium text-neutral-500">Tool:</span> {c.tool_metadata.description}</p>
                  )}
                  {c.tool_metadata.toolset && (
                    <p className="text-neutral-400"><span className="font-medium text-neutral-500">Toolset:</span> {c.tool_metadata.toolset}</p>
                  )}
                </div>
              )}
            </div>
            
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-neutral-500">Status: {c.status}</span>
              {(c.status === "DISCOVERED" || c.status === "PENDING_REVIEW") && (
                <div className="flex gap-2">
                  <Btn className="ghost" onClick={() => rejectMutation.mutate(c.id)} disabled={rejectMutation.isPending || approveMutation.isPending}>
                    Reject
                  </Btn>
                  <Btn className="primary" onClick={() => approveMutation.mutate(c.id)} disabled={rejectMutation.isPending || approveMutation.isPending}>
                    Approve
                  </Btn>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

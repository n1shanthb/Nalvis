import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { PageHead, Chip, Btn } from "../components/ui";

function formatRelativeTime(dateString: string) {
  if (!dateString) return "Unknown";
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (diffInSeconds < 60) return "Just now";
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes === 1 ? '' : 's'} ago`;
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
  const diffInDays = Math.floor(diffInHours / 24);
  return `${diffInDays} day${diffInDays === 1 ? '' : 's'} ago`;
}

function ArgumentsViewer({ argumentsJson }: { argumentsJson: string }) {
  const [expanded, setExpanded] = useState(false);
  
  let args = {};
  try {
    args = JSON.parse(argumentsJson);
  } catch (e) {
    // ignore
  }

  const keys = Object.keys(args);
  if (keys.length === 0) {
    return <div className="muted"><i>No arguments</i></div>;
  }

  const jsonString = JSON.stringify(args, null, 2);
  const isLarge = jsonString.split('\n').length > 5;

  return (
    <div className="console" style={{ marginTop: "0.5rem" }}>
      <div style={{ display: 'block', padding: '1rem' }}>
        <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: '0.85em', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {expanded || !isLarge ? jsonString : jsonString.split('\n').slice(0, 5).join('\n') + (isLarge && !expanded ? '\n...' : '')}
        </pre>
        {isLarge && (
          <button 
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} 
            style={{ 
              background: 'transparent', border: 'none', color: 'var(--accent)', 
              cursor: 'pointer', marginTop: '0.75rem', padding: 0, fontWeight: 600, fontSize: '0.82rem'
            }}
          >
            {expanded ? "Collapse details ▴" : "View details ▾"}
          </button>
        )}
      </div>
    </div>
  );
}

function ConfirmModal({ actionType, app, onConfirm, onCancel, isMutating }: any) {
  if (!app) return null;
  
  return (
    <div className="profile-overlay" onClick={!isMutating ? onCancel : undefined}>
      <div className="profile-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '32rem', padding: '1.75rem' }}>
        <h2 className="surface-title" style={{ fontSize: '1.15rem', marginBottom: '1.25rem' }}>
          {actionType === 'APPROVE' ? 'Approve this action?' : 'Reject this action?'}
        </h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '1.5rem', padding: '1rem', background: 'var(--surface-muted)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div>
            <div className="surface-label" style={{ marginBottom: '0.15rem' }}>Tool</div>
            <code style={{ color: 'var(--success)' }}>{app.tool}</code>
          </div>
          <div>
            <div className="surface-label" style={{ marginBottom: '0.15rem' }}>Agent</div>
            <div style={{ fontWeight: 500 }}>{app.agent_id}</div>
          </div>
          <div>
            <div className="surface-label" style={{ marginBottom: '0.15rem' }}>Project</div>
            <div style={{ fontWeight: 500 }}>{app.project_id}</div>
          </div>
        </div>
        
        <p className="lead" style={{ marginBottom: '1.75rem', fontSize: '0.9rem' }}>
          {actionType === 'APPROVE' 
            ? 'This action will be allowed to execute.' 
            : 'This action will be blocked and will not execute.'}
        </p>
        
        <div className="cta-row" style={{ justifyContent: 'flex-end', gap: '0.75rem' }}>
          <Btn onClick={onCancel} disabled={isMutating} className="ghost">Cancel</Btn>
          <Btn 
            onClick={onConfirm} 
            disabled={isMutating} 
            style={actionType === 'APPROVE' 
              ? { background: 'var(--success)', borderColor: 'var(--success)', color: '#fff' } 
              : { background: 'var(--danger)', borderColor: 'var(--danger)', color: '#fff' }
            }
          >
            {isMutating 
              ? (actionType === 'APPROVE' ? 'Approving...' : 'Rejecting...') 
              : (actionType === 'APPROVE' ? 'Approve' : 'Reject')}
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ApprovalModal({ app, onClose, onApproveRequest, onRejectRequest }: any) {
  if (!app) return null;
  const isPending = app.status === "PENDING";
  
  return (
    <div className="profile-overlay" onClick={onClose}>
      <div className="profile-modal" onClick={e => e.stopPropagation()}>
        <div className="surface-header" style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
          <h2 className="surface-title">Approval Details</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-muted)' }} aria-label="Close">✕</button>
        </div>
        
        <div className="split" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(12rem, 1fr))' }}>
          <div>
            <div className="surface-label">Tool</div>
            <code style={{ color: 'var(--success)' }}>{app.tool}</code>
          </div>
          <div>
            <div className="surface-label">Status</div>
            <Chip tone={
              app.status === "PENDING" ? "warning" : 
              app.status === "APPROVED" || app.status === "CONSUMED" ? "good" : 
              app.status === "REJECTED" ? "bad" : ""
            }>{app.status}</Chip>
          </div>
          <div>
            <div className="surface-label">Agent</div>
            <div>{app.agent_id}</div>
          </div>
          <div>
            <div className="surface-label">Project</div>
            <div>{app.project_id}</div>
          </div>
          <div>
            <div className="surface-label">Execution ID</div>
            <div className="muted" style={{ fontSize: '0.82rem', fontFamily: 'var(--mono)', wordBreak: 'break-all' }}>{app.execution_id || "N/A"}</div>
          </div>
          <div>
            <div className="surface-label">Requested At</div>
            <div>{new Date(app.created_at).toLocaleString()}</div>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="surface-label">Action Hash</div>
            <div className="muted" style={{ fontSize: '0.82rem', fontFamily: 'var(--mono)', wordBreak: 'break-all' }}>{app.action_hash || "N/A"}</div>
          </div>
        </div>
        
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
          <div className="surface-label">Arguments</div>
          <ArgumentsViewer argumentsJson={app.arguments_json} />
        </div>
        
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
          <div className="surface-label">Reason</div>
          <p className="lead">{app.reason || "Action matches a configured guardrail that requires human approval."}</p>
        </div>
        
        {isPending && (
          <div className="cta-row" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)', justifyContent: 'flex-end' }}>
            <Btn 
              onClick={() => onRejectRequest(app)}
              className="ghost"
              style={{ color: 'var(--danger)' }}
            >
              Reject action
            </Btn>
            <Btn 
              onClick={() => onApproveRequest(app)}
              style={{ background: 'var(--success)', borderColor: 'var(--success)', color: '#fff' }}
            >
              Approve action
            </Btn>
          </div>
        )}
      </div>
    </div>
  );
}

function ApprovalCard({ app, onApproveRequest, onRejectRequest, onClick }: any) {
  const isPending = app.status === "PENDING";
  
  return (
    <article 
      className="surface" 
      style={{ cursor: "pointer", position: "relative", borderColor: isPending ? "var(--warning)" : undefined }} 
      onClick={onClick}
    >
      <div className="surface-header">
        <h2 className="surface-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {isPending && <span style={{ color: 'var(--warning)' }}>⚠</span>}
          {isPending ? "Approval Required" : "Approval Decision"}
        </h2>
        <Chip tone={
          app.status === "PENDING" ? "warning" : 
          app.status === "APPROVED" || app.status === "CONSUMED" ? "good" : 
          app.status === "REJECTED" ? "bad" : ""
        }>{app.status}</Chip>
      </div>

      <div className="split" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(10rem, 1fr))' }}>
        <div>
          <div className="surface-label">Tool</div>
          <code style={{ color: 'var(--success)', border: 'none', background: 'var(--success-soft)' }}>{app.tool}</code>
        </div>
        <div>
          <div className="surface-label">Agent</div>
          <div style={{ wordBreak: 'break-all' }}>{app.agent_id}</div>
        </div>
        <div>
          <div className="surface-label">Project</div>
          <div style={{ wordBreak: 'break-all' }}>{app.project_id}</div>
        </div>
        <div>
          <div className="surface-label">Requested</div>
          <div>{formatRelativeTime(app.created_at)}</div>
        </div>
      </div>

      <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border)' }}>
        <div className="surface-label">Arguments</div>
        <ArgumentsViewer argumentsJson={app.arguments_json} />
      </div>
      
      <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border)' }}>
        <div className="surface-label">Why approval is required</div>
        <p className="lead" style={{ fontSize: '0.9rem' }}>{app.reason || "Action matches a configured guardrail that requires human approval."}</p>
      </div>
      
      {isPending && (
        <div className="cta-row" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)', justifyContent: 'flex-end' }} onClick={e => e.stopPropagation()}>
          <Btn 
            onClick={() => onRejectRequest(app)}
            className="ghost"
            style={{ color: 'var(--danger)' }}
          >
            Reject action
          </Btn>
          <Btn 
            onClick={() => onApproveRequest(app)}
            style={{ background: 'var(--success)', borderColor: 'var(--success)', color: '#fff' }}
          >
            Approve action
          </Btn>
        </div>
      )}
    </article>
  );
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState("PENDING");
  const [selectedApproval, setSelectedApproval] = useState<any>(null);
  
  const [confirmAction, setConfirmAction] = useState<{app: any, type: 'APPROVE' | 'REJECT'} | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const { data, isLoading, error } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<{ approvals: any[] }>("/approvals"),
    refetchInterval: 10000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => api(`/approvals/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setConfirmAction(null);
      setSelectedApproval(null);
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "The approval could not be completed. Please try again.");
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api(`/approvals/${id}/reject`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setConfirmAction(null);
      setSelectedApproval(null);
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "The rejection could not be completed. Please try again.");
    }
  });

  if (error) {
    return (
      <div className="main wide" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', textAlign: 'center' }}>
        <div style={{ color: 'var(--danger)', fontSize: '3rem', marginBottom: '1rem' }}>⚠</div>
        <h2 className="page-title">Unable to load approvals</h2>
        <p className="page-lead" style={{ maxWidth: '30rem', marginBottom: '2rem' }}>We couldn't retrieve pending agent actions. Please check your connection and try again.</p>
        <Btn onClick={() => queryClient.invalidateQueries({ queryKey: ["approvals"] })} className="primary">Retry</Btn>
      </div>
    );
  }

  const allApprovals = data?.approvals || [];

  const filteredApprovals = useMemo(() => {
    if (filter === "ALL") return allApprovals;
    if (filter === "PENDING") return allApprovals.filter(a => a.status === "PENDING");
    if (filter === "RESOLVED") return allApprovals.filter(a => a.status !== "PENDING");
    return allApprovals;
  }, [allApprovals, filter]);

  return (
    <div className="main wide" style={{ maxWidth: '64rem', margin: '0 auto' }}>
      <PageHead 
        title="Approval Center" 
        subtitle="Review agent actions that require human authorization." 
      />
      
      {errorMsg && (
        <div className="surface" style={{ borderColor: 'var(--danger)', background: 'var(--danger-soft)', color: 'var(--danger)', marginBottom: '1.5rem' }}>
          <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>Action failed</div>
          <div style={{ fontSize: '0.9rem' }}>{errorMsg}</div>
        </div>
      )}
      
      <div className="toolbar" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1.5rem' }}>
        {["PENDING", "RESOLVED", "ALL"].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              background: filter === f ? 'var(--color-ledger)' : 'transparent',
              color: filter === f ? 'var(--color-paper)' : 'var(--text-secondary)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              transition: 'background 0.2s, color 0.2s'
            }}
          >
            {f === "PENDING" ? "Pending" : f === "RESOLVED" ? "Resolved" : "All"}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {[1, 2].map(i => (
            <div key={i} className="surface" style={{ height: '16rem', opacity: 0.5 }} />
          ))}
        </div>
      ) : filteredApprovals.length === 0 ? (
        <div className="surface" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <div style={{ width: '4rem', height: '4rem', background: 'var(--success-soft)', color: 'var(--success)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', margin: '0 auto 1.5rem' }}>✓</div>
          <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.25rem', fontWeight: 700 }}>All clear</h2>
          <p className="muted" style={{ margin: 0 }}>No actions are currently waiting for human approval in this view.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {filteredApprovals.map((app: any) => (
            <ApprovalCard 
              key={app.id} 
              app={app} 
              onApproveRequest={() => setConfirmAction({ app, type: 'APPROVE' })}
              onRejectRequest={() => setConfirmAction({ app, type: 'REJECT' })}
              onClick={() => setSelectedApproval(app)}
            />
          ))}
        </div>
      )}
      
      {selectedApproval && !confirmAction && (
        <ApprovalModal 
          app={selectedApproval} 
          onClose={() => setSelectedApproval(null)} 
          onApproveRequest={(app: any) => setConfirmAction({ app, type: 'APPROVE' })}
          onRejectRequest={(app: any) => setConfirmAction({ app, type: 'REJECT' })}
        />
      )}
      
      {confirmAction && (
        <ConfirmModal 
          actionType={confirmAction.type}
          app={confirmAction.app}
          onCancel={() => setConfirmAction(null)}
          onConfirm={() => {
            setErrorMsg(null);
            if (confirmAction.type === 'APPROVE') {
              approveMutation.mutate(confirmAction.app.id);
            } else {
              rejectMutation.mutate(confirmAction.app.id);
            }
          }}
          isMutating={approveMutation.isPending || rejectMutation.isPending}
        />
      )}
    </div>
  );
}

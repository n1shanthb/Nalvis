import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

type Approval = {
  id: string;
  agent_id: string;
  tool: string;
  status: string;
  reason?: string;
};

type Toast = {
  id: string;
  agent_id: string;
  tool: string;
  reason?: string;
};

export function ApprovalSnackbar() {
  const seenRef = useRef<Set<string> | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const { data } = useQuery({
    queryKey: ["approvals", "snackbar"],
    queryFn: () => api<{ approvals: Approval[] }>("/approvals"),
    refetchInterval: 5000,
  });

  useEffect(() => {
    const pending = (data?.approvals || []).filter((a) => a.status === "PENDING");
    if (!seenRef.current) {
      seenRef.current = new Set(pending.map((a) => a.id));
      return;
    }
    const fresh = pending.filter((a) => !seenRef.current!.has(a.id));
    if (fresh.length === 0) return;
    fresh.forEach((a) => seenRef.current!.add(a.id));
    setToasts((prev) => [
      ...prev,
      ...fresh.map((a) => ({
        id: a.id,
        agent_id: a.agent_id,
        tool: a.tool,
        reason: a.reason,
      })),
    ]);
  }, [data]);

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  if (toasts.length === 0) return null;

  return (
    <div className="approval-snackbar-stack" aria-live="polite" aria-label="New approval requests">
      {toasts.map((toast) => (
        <div key={toast.id} className="approval-snackbar">
          <div className="approval-snackbar-body">
            <div className="approval-snackbar-title">Approval required</div>
            <div className="approval-snackbar-tool">
              <code>{toast.tool}</code>
            </div>
            <div className="approval-snackbar-agent">{toast.agent_id}</div>
            {toast.reason ? (
              <p className="approval-snackbar-reason">{toast.reason}</p>
            ) : null}
            <Link className="approval-snackbar-link" to="/approvals" onClick={() => dismiss(toast.id)}>
              Review in Approvals
            </Link>
          </div>
          <button
            type="button"
            className="approval-snackbar-close"
            aria-label="Dismiss"
            onClick={() => dismiss(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

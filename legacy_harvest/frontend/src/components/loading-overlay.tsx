import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/** Full-screen overlay — use only for explicit LLM/planning mutations, not navigation. */
type LoadingContextValue = {
  show: (title: string, steps?: string[]) => void;
  hide: () => void;
};

const LoadingContext = createContext<LoadingContextValue | null>(null);

export function LoadingProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState(false);
  const [title, setTitle] = useState("Working…");
  const [steps, setSteps] = useState<string[]>(["Working…"]);
  const [stepIndex, setStepIndex] = useState(0);

  const show = useCallback((nextTitle: string, nextSteps?: string[]) => {
    setTitle(nextTitle || "Working…");
    setSteps(nextSteps?.length ? nextSteps : ["Working…"]);
    setStepIndex(0);
    setActive(true);
  }, []);

  const hide = useCallback(() => setActive(false), []);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setStepIndex(i => (i + 1) % steps.length), 1300);
    return () => window.clearInterval(timer);
  }, [active, steps.length]);

  const value = useMemo(() => ({ show, hide }), [show, hide]);

  return (
    <LoadingContext.Provider value={value}>
      {children}
      <div className={`loading-screen${active ? " active" : ""}`} role="status" aria-live="polite">
        <div className="loading-box">
          <div className="loading-ring" aria-hidden="true" />
          <strong>{title}</strong>
          <span>{steps[stepIndex]}</span>
        </div>
      </div>
    </LoadingContext.Provider>
  );
}

export function useLoadingOverlay() {
  const context = useContext(LoadingContext);
  if (!context) throw new Error("useLoadingOverlay must be used inside LoadingProvider");
  return context;
}

import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

const STORAGE_KEY = "agentsuite-active-project";

function projectIdFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/projects\/([^/]+)/);
  return match?.[1];
}

export function useActiveProjectId(): string | undefined {
  const { projectId } = useParams();
  const { pathname } = useLocation();
  const fromRoute = projectId ?? projectIdFromPath(pathname);
  const [stored, setStored] = useState<string | undefined>(() => sessionStorage.getItem(STORAGE_KEY) ?? undefined);

  useEffect(() => {
    if (fromRoute) {
      sessionStorage.setItem(STORAGE_KEY, fromRoute);
      setStored(fromRoute);
    }
  }, [fromRoute]);

  return fromRoute ?? stored;
}

export function clearActiveProject() {
  sessionStorage.removeItem(STORAGE_KEY);
}

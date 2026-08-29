import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { get } from "./api/client";
import { ErrorState, Loading } from "../components/ui";

export function useApiQuery<T = Record<string, any>>(key: readonly unknown[], path: string, options: object = {}) {
  return useQuery<T>({ queryKey: key, queryFn: () => get<T>(path), ...options });
}

export function QueryBoundary<T>({ query, children }: { query: { isPending: boolean; error: Error | null; data?: T }; children: (data: T) => ReactNode }) {
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  return <>{children(query.data as T)}</>;
}

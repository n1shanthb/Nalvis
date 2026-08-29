import type { IntegrationHealth } from '@/lib/demo/models'

export type IntegrationsHealthResponse = {
  ok: boolean
  checked_at?: string | null
  integrations: IntegrationHealth[]
}

/**
 * Live control-plane integrations health (GitHub / Jira / Gmail / Calendar).
 * Always hits `/api` — not the demo store — so the ops console shows real status.
 */
export async function fetchIntegrationsHealth(
  signal?: AbortSignal,
): Promise<IntegrationsHealthResponse> {
  const res = await fetch('/api/integrations/health', {
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!res.ok) {
    throw new Error(`Integrations health failed (${res.status})`)
  }
  const body = (await res.json()) as IntegrationsHealthResponse
  return {
    ok: Boolean(body.ok),
    checked_at: body.checked_at ?? null,
    integrations: Array.isArray(body.integrations) ? body.integrations : [],
  }
}

import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { HealthBadge } from '@/components/shared/status'
import { formatRelative } from '@/lib/utils'
import { fetchIntegrationsHealth } from '@/lib/api/integrations'
import type { IntegrationHealth } from '@/lib/demo/models'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; integrations: IntegrationHealth[]; checkedAt: string | null; allOk: boolean }

export function IntegrationsPage() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(async (signal?: AbortSignal) => {
    setState({ status: 'loading' })
    try {
      const data = await fetchIntegrationsHealth(signal)
      if (signal?.aborted) return
      setState({
        status: 'ready',
        integrations: data.integrations,
        checkedAt: data.checked_at ?? null,
        allOk: data.ok,
      })
    } catch (err) {
      if (signal?.aborted) return
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to load integrations health',
      })
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    return () => ac.abort()
  }, [load])

  const integrations = state.status === 'ready' ? state.integrations : []
  const checkedAt = state.status === 'ready' ? state.checkedAt : null

  return (
    <div>
      <PageHeader
        title="Integrations Health"
        description="Live connector status from the control plane for GitHub, Jira, Gmail, and Calendar."
        actions={
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void load()}
            disabled={state.status === 'loading'}
          >
            <RefreshCw className={state.status === 'loading' ? 'animate-spin' : undefined} />
            Refresh
          </Button>
        }
      />

      {state.status === 'error' ? (
        <EmptyState
          title="Could not reach control plane"
          description={`${state.message}. Start the API (uvicorn apps.api.main:app) and try Refresh.`}
        />
      ) : null}

      {state.status === 'loading' && integrations.length === 0 ? (
        <EmptyState title="Checking connectors…" description="Querying /api/integrations/health." />
      ) : null}

      {state.status === 'ready' || integrations.length > 0 ? (
        <>
          <MetricStrip
            items={[
              {
                label: 'Healthy',
                value: integrations.filter((i) => i.status === 'healthy').length,
                tone: 'pass',
              },
              {
                label: 'Degraded',
                value: integrations.filter((i) => i.status === 'degraded').length,
                tone: 'warn',
              },
              {
                label: 'Down',
                value: integrations.filter((i) => i.status === 'down').length,
                tone: 'fail',
              },
              {
                label: 'Configured',
                value: integrations.filter((i) => i.credentialsConfigured).length,
              },
            ]}
          />
          {checkedAt ? (
            <p className="mb-4 text-xs text-[var(--color-muted)]">
              Checked {formatRelative(checkedAt)}
              {state.status === 'ready' && !state.allOk ? ' · one or more connectors need attention' : ''}
            </p>
          ) : null}

          {integrations.length === 0 ? (
            <EmptyState
              title="No integration health data"
              description="API returned an empty integrations list."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {integrations.map((integ) => (
                <IntegrationCard key={integ.name} integ={integ} />
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}

function IntegrationCard({ integ }: { integ: IntegrationHealth }) {
  const configEntries = Object.entries(integ.config ?? {}).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  )

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{integ.displayName}</CardTitle>
          <CardDescription className="font-mono">
            {integ.name}
            {integ.transport ? ` · ${integ.transport}` : ''}
          </CardDescription>
        </div>
        <HealthBadge status={integ.status} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-[var(--color-fg-dim)]">
        <Row label="Credentials" value={integ.credentialsConfigured ? 'Configured' : 'Missing'} />
        <Row
          label="Last success"
          value={integ.lastSuccessfulCallAt ? formatRelative(integ.lastSuccessfulCallAt) : 'Never'}
        />
        <Row
          label="Rate limit remaining"
          value={integ.rateLimitRemaining == null ? '—' : String(integ.rateLimitRemaining)}
        />
        <Row
          label="Rate limit reset"
          value={integ.rateLimitResetAt ? formatRelative(integ.rateLimitResetAt) : '—'}
        />
        <Row
          label="Latency p50"
          value={integ.latencyMsP50 == null ? '—' : `${integ.latencyMsP50} ms`}
        />
        {integ.lastError ? (
          <div className="rounded-md border border-[var(--color-fail)]/30 bg-[var(--color-fail)]/10 p-2 text-xs text-[var(--color-fail)]">
            {integ.lastError}
          </div>
        ) : null}

        {configEntries.length > 0 ? (
          <div className="pt-2">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
              Config & settings
            </p>
            {configEntries.map(([key, value]) => (
              <Row key={key} label={formatConfigKey(key)} value={formatConfigValue(value)} />
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)]/50 py-1.5 last:border-0">
      <span className="text-xs text-[var(--color-muted)]">{label}</span>
      <span className="max-w-[60%] truncate text-right font-mono text-xs" title={value}>
        {value}
      </span>
    </div>
  )
}

function formatConfigKey(key: string): string {
  return key.replaceAll('_', ' ')
}

function formatConfigValue(value: string | number | boolean | null | undefined): string {
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (value == null || value === '') return '—'
  return String(value)
}

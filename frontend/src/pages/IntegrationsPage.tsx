import { useCallback, useEffect, useState } from 'react'
import { Check, Copy, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { HealthBadge } from '@/components/shared/status'
import { formatRelative } from '@/lib/utils'
import { fetchIntegrationsHealth } from '@/lib/api/integrations'
import {
  fetchTunnelStatus,
  startTunnel,
  stopTunnel,
  type TunnelStatus,
} from '@/lib/api/tunnel'
import type { IntegrationHealth } from '@/lib/demo/models'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; integrations: IntegrationHealth[]; checkedAt: string | null; allOk: boolean }

const WEBHOOK_LABELS: Array<{ key: keyof TunnelStatus['urls']; label: string }> = [
  { key: 'github', label: 'GitHub webhook' },
  { key: 'jira', label: 'Jira webhook' },
  { key: 'gmail', label: 'Gmail Pub/Sub push' },
]

export function IntegrationsPage() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [tunnel, setTunnel] = useState<TunnelStatus | null>(null)
  const [tunnelBusy, setTunnelBusy] = useState(false)
  const [tunnelError, setTunnelError] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

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

  const refreshTunnel = useCallback(async () => {
    try {
      const st = await fetchTunnelStatus()
      setTunnel(st)
      setTunnelError(null)
      return st
    } catch (err) {
      setTunnelError(err instanceof Error ? err.message : 'Tunnel status failed')
      return null
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    void refreshTunnel()
    return () => ac.abort()
  }, [load, refreshTunnel])

  // Poll while tunnel is starting until public URL appears
  useEffect(() => {
    if (!tunnel) return
    const needPoll =
      tunnel.status === 'starting' || (tunnel.running && !tunnel.public_base)
    if (!needPoll) return
    const id = window.setInterval(() => {
      void refreshTunnel()
    }, 1500)
    return () => window.clearInterval(id)
  }, [tunnel, refreshTunnel])

  async function onStartTunnel() {
    setTunnelBusy(true)
    setTunnelError(null)
    try {
      const st = await startTunnel()
      setTunnel(st)
      // URL often arrives a second later from cloudflared stdout
      window.setTimeout(() => void refreshTunnel(), 1200)
      window.setTimeout(() => void refreshTunnel(), 3000)
    } catch (err) {
      setTunnelError(err instanceof Error ? err.message : 'Failed to start tunnel')
    } finally {
      setTunnelBusy(false)
    }
  }

  async function onStopTunnel() {
    setTunnelBusy(true)
    setTunnelError(null)
    try {
      setTunnel(await stopTunnel())
    } catch (err) {
      setTunnelError(err instanceof Error ? err.message : 'Failed to stop tunnel')
    } finally {
      setTunnelBusy(false)
    }
  }

  async function copyUrl(key: string, url: string) {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1600)
    } catch {
      setTunnelError('Clipboard copy failed — select the URL manually')
    }
  }

  const integrations = state.status === 'ready' ? state.integrations : []
  const checkedAt = state.status === 'ready' ? state.checkedAt : null
  const running = Boolean(tunnel?.running && tunnel.public_base)
  const starting = tunnel?.status === 'starting' || (tunnel?.running && !tunnel.public_base)

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
            onClick={() => {
              void load()
              void refreshTunnel()
            }}
            disabled={state.status === 'loading'}
          >
            <RefreshCw className={state.status === 'loading' ? 'animate-spin' : undefined} />
            Refresh
          </Button>
        }
      />

      <Card className="mb-6">
        <CardHeader>
          <div>
            <CardTitle>Inbound webhook tunnel</CardTitle>
            <CardDescription>
              Starts a Cloudflare quick tunnel to this machine&apos;s API. Copy the three webhook URLs
              into GitHub, Jira, and Gmail Pub/Sub. Quick URLs change when you restart the tunnel.
            </CardDescription>
          </div>
          <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
            {tunnel?.status ?? '…'}
          </span>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              disabled={tunnelBusy || running || starting || tunnel?.binary === false}
              onClick={() => void onStartTunnel()}
            >
              {starting ? 'Starting…' : 'Start tunnel'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={tunnelBusy || !tunnel?.running}
              onClick={() => void onStopTunnel()}
            >
              Stop tunnel
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={tunnelBusy}
              onClick={() => void refreshTunnel()}
            >
              Refresh status
            </Button>
          </div>

          {tunnel?.binary === false ? (
            <div
              className="rounded-md border border-[var(--color-warn)]/30 bg-[var(--color-warn)]/10 px-3 py-2 text-sm text-[var(--color-warn)]"
              role="status"
            >
              {tunnel.install_hint ||
                'cloudflared not found on PATH. Install it, then Refresh status.'}
            </div>
          ) : null}

          {tunnelError ? (
            <div
              className="rounded-md border border-[var(--color-fail)]/30 bg-[var(--color-fail)]/10 px-3 py-2 text-sm text-[var(--color-fail)]"
              role="alert"
            >
              {tunnelError}
            </div>
          ) : null}

          {tunnel?.error ? (
            <div
              className="rounded-md border border-[var(--color-fail)]/30 bg-[var(--color-fail)]/10 px-3 py-2 text-sm text-[var(--color-fail)]"
              role="alert"
            >
              {tunnel.error}
            </div>
          ) : null}

          {tunnel?.url_changed ? (
            <p className="text-xs text-[var(--color-warn)]">
              Public URL changed since last run — update provider webhook settings.
            </p>
          ) : null}

          <div className="space-y-2">
            <Row label="Public base" value={tunnel?.public_base || '— (start tunnel)'} />
            <Row label="Local API" value={tunnel?.local_url || 'http://127.0.0.1:8000'} />
          </div>

          <div className="space-y-2 pt-1">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
              Webhook URLs
            </p>
            {WEBHOOK_LABELS.map(({ key, label }) => {
              const url = tunnel?.urls?.[key] || ''
              const ready = Boolean(url)
              return (
                <div
                  key={key}
                  className="flex flex-col gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-3 sm:flex-row sm:items-center"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-xs text-[var(--color-muted)]">{label}</div>
                    <div
                      className="mt-0.5 break-all font-mono text-xs text-[var(--color-fg)]"
                      title={url || undefined}
                    >
                      {ready ? url : 'Start tunnel to generate URL'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={!ready}
                    onClick={() => void copyUrl(key, url)}
                    aria-label={`Copy ${label} URL`}
                  >
                    {copiedKey === key ? (
                      <>
                        <Check className="h-4 w-4" aria-hidden />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4" aria-hidden />
                        Copy
                      </>
                    )}
                  </Button>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

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

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { HealthBadge } from '@/components/shared/status'
import { formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'

export function IntegrationsPage() {
  const integrations = useDemoStore((s) => s.integrations)

  return (
    <div>
      <PageHeader
        title="Integrations Health"
        description="Live connector status from the control plane. Empty means health has not been reported yet."
      />
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

      {integrations.length === 0 ? (
        <EmptyState
          title="No integration health data"
          description="Nothing to show until the API reports GitHub, Jira, Gmail, and Calendar status."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {integrations.map((integ) => (
            <Card key={integ.name}>
              <CardHeader>
                <div>
                  <CardTitle>{integ.displayName}</CardTitle>
                  <CardDescription className="font-mono">{integ.name}</CardDescription>
                </div>
                <HealthBadge status={integ.status} />
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-[var(--color-fg-dim)]">
                <Row
                  label="Credentials"
                  value={integ.credentialsConfigured ? 'Configured' : 'Missing'}
                />
                <Row
                  label="Last success"
                  value={
                    integ.lastSuccessfulCallAt
                      ? formatRelative(integ.lastSuccessfulCallAt)
                      : 'Never'
                  }
                />
                <Row
                  label="Rate limit remaining"
                  value={
                    integ.rateLimitRemaining == null ? '—' : String(integ.rateLimitRemaining)
                  }
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
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)]/50 py-1.5 last:border-0">
      <span className="text-xs text-[var(--color-muted)]">{label}</span>
      <span className="text-xs">{value}</span>
    </div>
  )
}

import { cn } from '@/lib/utils'
import type { ValidationVerdict, RunStatus, JobStatus, AgentStatus, IntegrationHealthStatus } from '@/lib/demo/models'
import { Badge } from '@/components/ui/badge'

export function VerdictBadge({ verdict }: { verdict: ValidationVerdict }) {
  const variant = verdict === 'PASS' ? 'pass' : verdict === 'FAIL' ? 'fail' : 'none'
  return <Badge variant={variant}>{verdict.replace('_', ' ')}</Badge>
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, 'accent' | 'pass' | 'fail' | 'warn' | 'default'> = {
    queued: 'default',
    running: 'accent',
    succeeded: 'pass',
    failed: 'fail',
    partial: 'warn',
  }
  return <Badge variant={map[status]}>{status}</Badge>
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const map: Record<JobStatus, 'accent' | 'pass' | 'fail' | 'warn' | 'default'> = {
    queued: 'default',
    running: 'accent',
    succeeded: 'pass',
    failed: 'fail',
    blocked_for_approval: 'warn',
  }
  return <Badge variant={map[status]}>{status.replaceAll('_', ' ')}</Badge>
}

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const map: Record<AgentStatus, 'pass' | 'default' | 'fail' | 'warn'> = {
    active: 'pass',
    idle: 'default',
    disabled: 'warn',
    error: 'fail',
    unsupported: 'warn',
  }
  const label =
    status === 'unsupported' ? 'not supported — connect system to activate' : status
  return <Badge variant={map[status]}>{label}</Badge>
}

export function HealthBadge({ status }: { status: IntegrationHealthStatus }) {
  const map: Record<IntegrationHealthStatus, 'pass' | 'warn' | 'fail' | 'none'> = {
    healthy: 'pass',
    degraded: 'warn',
    down: 'fail',
    unknown: 'none',
  }
  return <Badge variant={map[status]}>{status}</Badge>
}

export function FilterChips<T extends string>({
  options,
  value,
  onChange,
  allLabel = 'All',
}: {
  options: { value: T; label: string }[]
  value: T | 'all'
  onChange: (v: T | 'all') => void
  allLabel?: string
}) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filters">
      <button
        type="button"
        onClick={() => onChange('all')}
        className={cn(
          'rounded-full border px-3 py-1 text-xs transition-colors',
          value === 'all'
            ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
            : 'border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-fg)]',
        )}
      >
        {allLabel}
      </button>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-full border px-3 py-1 text-xs transition-colors',
            value === o.value
              ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
              : 'border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-fg)]',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

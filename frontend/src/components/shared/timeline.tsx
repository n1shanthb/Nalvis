import { cn, formatRelative } from '@/lib/utils'
import type { TimelineEvent } from '@/lib/demo/models'

const kindColor: Record<TimelineEvent['kind'], string> = {
  queued: 'bg-[var(--color-muted)]',
  started: 'bg-[var(--color-accent)]',
  approval: 'bg-[var(--color-warn)]',
  tool_call: 'bg-[var(--color-accent-2)]',
  validation: 'bg-[var(--color-pass)]',
  completed: 'bg-[var(--color-pass)]',
  failed: 'bg-[var(--color-fail)]',
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-[var(--color-muted)]">No timeline events yet.</p>
  }

  return (
    <ol className="relative space-y-4 border-l border-[var(--color-border)] pl-5">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span
            className={cn(
              'absolute -left-[1.4rem] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-[var(--color-surface)]',
              kindColor[e.kind],
            )}
            aria-hidden
          />
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="text-sm text-[var(--color-fg)]">{e.label}</div>
            <time className="text-[11px] text-[var(--color-muted)]" dateTime={e.at}>
              {formatRelative(e.at)}
            </time>
          </div>
          <div className="mt-0.5 text-[11px] uppercase tracking-wide text-[var(--color-muted)]">
            {e.kind.replace('_', ' ')}
            {e.jobId ? ` · ${e.jobId}` : ''}
          </div>
          {e.meta ? (
            <pre className="mt-2 overflow-auto rounded-md bg-[var(--color-bg)] p-2 text-[11px] text-[var(--color-fg-dim)]">
              {JSON.stringify(e.meta, null, 2)}
            </pre>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

export function DagPanel({
  jobs,
}: {
  jobs: { id: string; title: string; status: string; jobType: string }[]
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {jobs.map((j, idx) => (
        <div
          key={j.id}
          className="relative rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3"
        >
          <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
            Step {idx + 1} · {j.jobType}
          </div>
          <div className="mt-1 text-sm font-medium">{j.title}</div>
          <div className="mt-2 text-xs text-[var(--color-muted)]">
            {j.id} · {j.status.replaceAll('_', ' ')}
          </div>
        </div>
      ))}
    </div>
  )
}

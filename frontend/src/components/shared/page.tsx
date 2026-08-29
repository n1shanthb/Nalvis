import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-[var(--color-fg)]">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-muted)]">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function MetricStrip({
  items,
}: {
  items: { label: string; value: string | number; hint?: string; tone?: 'default' | 'pass' | 'fail' | 'warn' | 'accent' }[]
}) {
  const toneClass = {
    default: 'text-[var(--color-fg)]',
    pass: 'text-[var(--color-pass)]',
    fail: 'text-[var(--color-fail)]',
    warn: 'text-[var(--color-warn)]',
    accent: 'text-[var(--color-accent)]',
  } as const

  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3"
        >
          <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">{item.label}</div>
          <div className={cn('mt-1 text-2xl font-semibold tabular-nums', toneClass[item.tone ?? 'default'])}>
            {item.value}
          </div>
          {item.hint ? <div className="mt-1 text-xs text-[var(--color-muted)]">{item.hint}</div> : null}
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]/50 px-6 py-12 text-center">
      <div className="text-sm font-medium text-[var(--color-fg)]">{title}</div>
      {description ? <p className="mt-1 text-xs text-[var(--color-muted)]">{description}</p> : null}
    </div>
  )
}

export function LoadingState({ label = 'Loading console…' }: { label?: string }) {
  return (
    <div className="flex h-40 items-center justify-center text-sm text-[var(--color-muted)]" role="status">
      {label}
    </div>
  )
}

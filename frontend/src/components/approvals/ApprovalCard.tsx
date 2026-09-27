import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/input'
import { formatRelative } from '@/lib/utils'
import { parseActionPayload, resolveApprovalContext, systemBadgeTone } from '@/lib/approvalDetails'
import type { ApprovalItem } from '@/lib/demo/models'

export function ApprovalCard({
  projectId,
  item,
  agentName,
  editValue,
  onEditChange,
  onApprove,
  onDeny,
  onEdit,
}: {
  projectId: string
  item: ApprovalItem
  agentName: string
  editValue: string
  onEditChange: (v: string) => void
  onApprove: () => void
  onDeny: () => void
  onEdit: () => void
}) {
  const pending = item.decision === 'pending'
  const ctx = resolveApprovalContext(item)
  const [showRaw, setShowRaw] = useState(false)
  const action = ctx.requestedAction ?? parseActionPayload(item.diffPreview.after)

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={systemBadgeTone(ctx.system)}>{ctx.actionLabel}</Badge>
              <Badge variant={pending ? 'warn' : item.decision === 'denied' ? 'fail' : 'pass'}>
                {item.decision}
              </Badge>
            </div>
            <CardTitle className="text-lg">{item.title || ctx.summary}</CardTitle>
            <CardDescription className="space-y-1">
              <span className="block">
                Agent:{' '}
                <Link
                  className="text-[var(--color-accent)] hover:underline"
                  to={`/projects/${projectId}/agents/${item.agentId}`}
                >
                  {agentName}
                </Link>
              </span>
              <span className="block">
                Run:{' '}
                <Link
                  className="text-[var(--color-accent)] hover:underline"
                  to={`/projects/${projectId}/runs/${item.runId}`}
                >
                  {item.runId}
                </Link>
                {' · '}
                Job {item.jobId}
              </span>
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/60 p-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]">
            Why approval is required
          </h3>
          <p className="text-sm text-[var(--color-fg)]">{item.intentSummary || ctx.summary}</p>
        </section>

        {ctx.trigger ? (
          <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/40 p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]">
              Inbound trigger
            </h3>
            <p className="mb-3 text-sm font-medium text-[var(--color-fg)]">{ctx.trigger.title}</p>
            <dl className="grid gap-2 sm:grid-cols-2">
              {ctx.trigger.rows.map((row) => (
                <div key={row.label}>
                  <dt className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                    {row.label}
                  </dt>
                  <dd className="text-sm text-[var(--color-fg-dim)] whitespace-pre-wrap">{row.value}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]">
            Proposed action
          </h3>
          <dl className="grid gap-3 sm:grid-cols-2">
            {ctx.fields.map((field) => (
              <div key={field.label} className={field.label === 'Inbound preview' ? 'sm:col-span-2' : ''}>
                <dt className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                  {field.label}
                </dt>
                <dd
                  className={`mt-0.5 text-sm text-[var(--color-fg)] whitespace-pre-wrap ${
                    field.mono ? 'font-mono text-xs' : ''
                  }`}
                >
                  {field.link ? (
                    <a
                      href={field.link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--color-accent)] hover:underline"
                    >
                      {field.value}
                    </a>
                  ) : (
                    field.value
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {ctx.links.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {ctx.links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-[var(--color-accent)] hover:underline"
              >
                {link.label} ↗
              </a>
            ))}
          </div>
        ) : null}

        {ctx.impact.length > 0 ? (
          <section className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
              Impact if approved
            </h3>
            <ul className="list-disc space-y-1 pl-4 text-sm text-[var(--color-fg-dim)]">
              {ctx.impact.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {pending && ctx.editableKey ? (
          <section>
            <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              {ctx.editableLabel ?? 'Edit before sending'} (optional)
            </div>
            <Textarea
              aria-label={`${ctx.editableLabel ?? 'Edit'} for ${item.id}`}
              value={editValue}
              onChange={(e) => onEditChange(e.target.value)}
              className="min-h-[120px] font-sans"
              placeholder={ctx.editableDefault || 'Enter message body…'}
            />
            <p className="mt-1 text-[11px] text-[var(--color-muted)]">
              Approve uses the default text above unless you edit &amp; approve with changes.
            </p>
          </section>
        ) : null}

        {!pending && item.editedPayload ? (
          <section>
            <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              Approved with edits
            </div>
            <pre className="overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs whitespace-pre-wrap">
              {item.editedPayload}
            </pre>
          </section>
        ) : null}

        <div>
          <button
            type="button"
            onClick={() => setShowRaw((s) => !s)}
            className="text-xs text-[var(--color-muted)] hover:text-[var(--color-fg)]"
          >
            {showRaw ? 'Hide' : 'Show'} technical payload
          </button>
          {showRaw ? (
            <pre className="mt-2 overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs text-[var(--color-fg-dim)] whitespace-pre-wrap">
              {JSON.stringify(action, null, 2)}
            </pre>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--color-border)] pt-3">
          <span className="text-[11px] text-[var(--color-muted)]">
            Created {formatRelative(item.createdAt)}
            {item.decidedAt ? ` · decided ${formatRelative(item.decidedAt)}` : ''}
          </span>
          {pending ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="success" onClick={onApprove}>
                Approve
              </Button>
              <Button variant="secondary" onClick={onEdit}>
                Edit &amp; approve
              </Button>
              <Button variant="danger" onClick={onDeny}>
                Deny
              </Button>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

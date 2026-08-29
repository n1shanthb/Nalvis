import { useMemo, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { useDemoStore } from '@/lib/store'

export function ContextStudioPage() {
  const [raw, setRaw] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const ingestContext = useDemoStore((s) => s.ingestContext)
  const docs = useDemoStore((s) => s.contextDocuments)
  const workspaces = useDemoStore((s) => s.workspaces)
  const latest = docs[0]

  const metrics = useMemo(
    () => [
      { label: 'Workspaces', value: workspaces.length, tone: 'accent' as const },
      {
        label: 'Products derived',
        value: latest?.parsePreview?.workspacesDerived ?? 0,
      },
      { label: 'Repos in scope', value: latest?.parsePreview?.repos.length ?? 0 },
      {
        label: 'Parse warnings',
        value: latest?.parsePreview?.warnings.length ?? 0,
        tone: (latest?.parsePreview?.warnings.length ? 'warn' : 'pass') as 'warn' | 'pass',
      },
    ],
    [workspaces, latest],
  )

  async function runParse(source: 'paste' | 'upload', content = raw) {
    if (!content.trim()) {
      setError('Nothing to parse — paste JSON/text or upload a file.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await ingestContext(content, source)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Parse failed')
    } finally {
      setBusy(false)
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return
    const text = await file.text()
    setRaw(text)
    await runParse('upload', text)
  }

  return (
    <div>
      <PageHeader
        title="Context Studio"
        description="Upload company KG JSON or paste text. No sample payload is preloaded — empty means nothing ingested yet."
      />

      <MetricStrip items={metrics} />

      {error ? (
        <div
          className="mb-4 rounded-lg border border-[var(--color-fail)]/30 bg-[var(--color-fail)]/10 px-3 py-2 text-sm text-[var(--color-fail)]"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Ingest</CardTitle>
            <CardDescription>Paste JSON/text or upload a `.json` file from your company.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              aria-label="Company context input"
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              placeholder='{"company":"…","products":[…]}'
              spellCheck={false}
            />
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy || !raw.trim()} onClick={() => void runParse('paste')}>
                Parse paste
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="h-4 w-4" aria-hidden />
                Upload JSON
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json,.txt"
                className="hidden"
                aria-label="Upload context file"
                onChange={(e) => void onFile(e.target.files?.[0])}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Parse preview</CardTitle>
            <CardDescription>
              {latest
                ? `${latest.name} · ${latest.source} · ${latest.parsedAt ?? 'unparsed'}`
                : 'No documents ingested yet'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {latest?.parsePreview ? (
              <div className="space-y-4 text-sm">
                <div>
                  <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                    Products
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {latest.parsePreview.products.length === 0 ? (
                      <span className="text-xs text-[var(--color-muted)]">None</span>
                    ) : (
                      latest.parsePreview.products.map((p) => (
                        <Badge key={p} variant="accent">
                          {p}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
                <PreviewList label="Repos" items={latest.parsePreview.repos} />
                <PreviewList label="Jira projects" items={latest.parsePreview.jiraProjects} />
                <PreviewList label="Calendars" items={latest.parsePreview.calendars} />
                <PreviewList label="Email groups" items={latest.parsePreview.emailGroups} />
                <PreviewList label="Stakeholders" items={latest.parsePreview.stakeholders} />
                {latest.parsePreview.warnings.length > 0 ? (
                  <div className="rounded-md border border-[var(--color-warn)]/30 bg-[var(--color-warn)]/10 p-3 text-xs text-[var(--color-warn)]">
                    {latest.parsePreview.warnings.map((w) => (
                      <div key={w}>{w}</div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No parse output"
                description="Ingest real company context to see derived scopes."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Derived workspaces</CardTitle>
          <CardDescription>
            Persisted product workspaces from the store (empty until backend or ingest creates them).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {workspaces.length === 0 ? (
            <EmptyState
              title="No workspaces yet"
              description="Parse preview may show products, but workspace records stay empty until the control plane creates them."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-3">
              {workspaces.map((ws) => (
                <div
                  key={ws.id}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
                >
                  <div className="font-medium">{ws.name}</div>
                  <p className="mt-1 text-xs text-[var(--color-muted)]">{ws.description}</p>
                  <div className="mt-3 space-y-1 text-[11px] text-[var(--color-fg-dim)]">
                    <div>Repos: {ws.scope.repos.join(', ') || '—'}</div>
                    <div>Jira: {ws.scope.jiraKeys.join(', ') || '—'}</div>
                    <div>Cal: {ws.scope.calendars.join(', ') || '—'}</div>
                  </div>
                  <Link
                    className="mt-3 inline-block text-xs text-[var(--color-accent)] hover:underline"
                    to={`/projects/${ws.id}`}
                  >
                    Open project →
                  </Link>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function PreviewList({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      {items.length === 0 ? (
        <div className="text-xs text-[var(--color-muted)]">—</div>
      ) : (
        <ul className="space-y-0.5 font-mono text-xs text-[var(--color-fg-dim)]">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

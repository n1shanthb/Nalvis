import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/input'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { FilterChips } from '@/components/shared/status'
import { Badge } from '@/components/ui/badge'
import { formatRelative } from '@/lib/utils'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import type { ApprovalDecision, ApprovalItem } from '@/lib/demo/models'

export function ApprovalsPage() {
  const { projectId = '' } = useParams()
  const { workspace, approvals } = useProjectData(projectId)
  const decideApproval = useDemoStore((s) => s.decideApproval)
  const agents = useDemoStore((s) => s.agents)
  const [filter, setFilter] = useState<ApprovalDecision | 'all'>('pending')
  const [editing, setEditing] = useState<Record<string, string>>({})

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  const filtered =
    filter === 'all' ? approvals : approvals.filter((a) => a.decision === filter)

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Approvals`}
        description="HIL inbox for this project only — approve, deny, or edit governed write actions."
      />
      <MetricStrip
        items={[
          {
            label: 'Pending',
            value: approvals.filter((a) => a.decision === 'pending').length,
            tone: 'warn',
          },
          {
            label: 'Approved',
            value: approvals.filter((a) => a.decision === 'approved').length,
            tone: 'pass',
          },
          {
            label: 'Denied',
            value: approvals.filter((a) => a.decision === 'denied').length,
            tone: 'fail',
          },
          {
            label: 'Edited',
            value: approvals.filter((a) => a.decision === 'edited').length,
            tone: 'accent',
          },
        ]}
      />

      <div className="mb-4">
        <FilterChips
          value={filter}
          onChange={setFilter}
          options={(['pending', 'approved', 'denied', 'edited'] as ApprovalDecision[]).map((d) => ({
            value: d,
            label: d,
          }))}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="Inbox clear for this project" description="No approvals for this filter." />
      ) : (
        <div className="space-y-4">
          {filtered.map((item) => (
            <ApprovalCard
              key={item.id}
              projectId={projectId}
              item={item}
              agentName={agents.find((a) => a.id === item.agentId)?.name ?? item.agentId}
              editValue={editing[item.id] ?? item.diffPreview.after}
              onEditChange={(v) => setEditing((s) => ({ ...s, [item.id]: v }))}
              onApprove={() => void decideApproval(item.id, 'approved')}
              onDeny={() => void decideApproval(item.id, 'denied')}
              onEdit={() =>
                void decideApproval(item.id, 'edited', editing[item.id] ?? item.diffPreview.after)
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ApprovalCard({
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
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{item.title}</CardTitle>
          <CardDescription>
            {item.jobType} ·{' '}
            <Link
              className="text-[var(--color-accent)] hover:underline"
              to={`/projects/${projectId}/agents/${item.agentId}`}
            >
              {agentName}
            </Link>{' '}
            ·{' '}
            <Link
              className="text-[var(--color-accent)] hover:underline"
              to={`/projects/${projectId}/runs/${item.runId}`}
            >
              {item.runId}
            </Link>
          </CardDescription>
        </div>
        <Badge variant={pending ? 'warn' : item.decision === 'denied' ? 'fail' : 'pass'}>
          {item.decision}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-[var(--color-fg-dim)]">{item.intentSummary}</p>
        <div className="grid gap-3 md:grid-cols-2">
          <DiffBlock label="Before" value={item.diffPreview.before} />
          {pending ? (
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
                After (editable)
              </div>
              <Textarea
                aria-label={`Edit payload for ${item.id}`}
                value={editValue}
                onChange={(e) => onEditChange(e.target.value)}
                className="min-h-[100px]"
              />
            </div>
          ) : (
            <DiffBlock label="After" value={item.editedPayload ?? item.diffPreview.after} />
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[11px] text-[var(--color-muted)]">
            Created {formatRelative(item.createdAt)}
            {item.decidedAt ? ` · decided ${formatRelative(item.decidedAt)}` : ''}
          </span>
          {pending ? (
            <div className="flex gap-2">
              <Button variant="success" onClick={onApprove}>
                Approve
              </Button>
              <Button variant="secondary" onClick={onEdit}>
                Edit & approve
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

function DiffBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">{label}</div>
      <pre className="overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs text-[var(--color-fg-dim)] whitespace-pre-wrap">
        {value}
      </pre>
    </div>
  )
}

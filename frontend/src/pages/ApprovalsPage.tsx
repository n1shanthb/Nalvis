import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageHeader, MetricStrip, EmptyState } from '@/components/shared/page'
import { FilterChips } from '@/components/shared/status'
import { agentDisplayName } from '@/lib/utils'
import { resolveApprovalContext } from '@/lib/approvalDetails'
import { useDemoStore } from '@/lib/store'
import { useProjectData } from '@/lib/useProjectData'
import { ApprovalCard } from '@/components/approvals/ApprovalCard'
import type { ApprovalDecision } from '@/lib/demo/models'

export function ApprovalsPage() {
  const { projectId = '' } = useParams()
  const { workspace, approvals } = useProjectData(projectId)
  const decideApproval = useDemoStore((s) => s.decideApproval)
  const hydrate = useDemoStore((s) => s.hydrate)
  const agents = useDemoStore((s) => s.agents)
  const [filter, setFilter] = useState<ApprovalDecision | 'all'>('pending')
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    void hydrate()
  }, [hydrate, projectId])

  // Seed editable body text from approval context defaults
  useEffect(() => {
    setEditing((prev) => {
      const next = { ...prev }
      for (const item of approvals) {
        if (next[item.id] !== undefined) continue
        const ctx = resolveApprovalContext(item)
        if (ctx.editableDefault) next[item.id] = ctx.editableDefault
      }
      return next
    })
  }, [approvals])

  if (!workspace) {
    return <EmptyState title="Project not found" />
  }

  const filtered =
    filter === 'all' ? approvals : approvals.filter((a) => a.decision === filter)

  return (
    <div>
      <PageHeader
        title={`${workspace.name} · Approvals`}
        description="Review what each agent will do externally — trigger, target, message, and impact — before approving writes."
        actions={
          <Button
            variant="secondary"
            disabled={refreshing}
            onClick={async () => {
              setRefreshing(true)
              try {
                await hydrate()
              } finally {
                setRefreshing(false)
              }
            }}
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
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
          {filtered.map((item) => {
            const agent = agents.find((a) => a.id === item.agentId)
            const ctx = resolveApprovalContext(item)
            const defaultEdit = ctx.editableDefault ?? ''
            return (
              <ApprovalCard
                key={item.id}
                projectId={projectId}
                item={item}
                agentName={agentDisplayName(agent?.name ?? item.agentId, workspace.name)}
                editValue={editing[item.id] ?? defaultEdit}
                onEditChange={(v) => setEditing((s) => ({ ...s, [item.id]: v }))}
                onApprove={() => void decideApproval(item.id, 'approved')}
                onDeny={() => void decideApproval(item.id, 'denied')}
                onEdit={() =>
                  void decideApproval(
                    item.id,
                    'edited',
                    editing[item.id] ?? defaultEdit,
                  )
                }
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

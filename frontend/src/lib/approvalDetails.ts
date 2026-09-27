import type { ApprovalContext, ApprovalItem } from '@/lib/demo/models'

const DEFAULT_GMAIL_REPLY =
  'Thank you for your message. We have received it and will follow up shortly.'

const JOB_LABELS: Record<string, string> = {
  'gmail.send_email': 'Gmail · Send or reply',
  'github.create_issue': 'GitHub · Create issue',
  'github.comment_issue': 'GitHub · Comment on issue',
  'github.review_pr': 'GitHub · Pull request review',
  'github.create_or_update_workflow': 'GitHub · CI workflow change',
  'jira.create_ticket': 'Jira · Create ticket',
  'jira.transition_ticket': 'Jira · Transition ticket',
  'calendar.create_event': 'Calendar · Create event',
  'calendar.update_event': 'Calendar · Update event',
}

export function parseActionPayload(raw: string): Record<string, unknown> {
  const text = (raw || '').trim()
  if (!text) return {}
  try {
    return JSON.parse(text) as Record<string, unknown>
  } catch {
    try {
      const normalized = text
        .replace(/'/g, '"')
        .replace(/\bNone\b/g, 'null')
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
      return JSON.parse(normalized) as Record<string, unknown>
    } catch {
      return {}
    }
  }
}

/** Resolve rich context — API field, diffPreview.context, or client fallback for legacy rows. */
export function resolveApprovalContext(item: ApprovalItem): ApprovalContext {
  const fromApi = item.context ?? item.diffPreview?.context
  if (fromApi && fromApi.fields?.length) return fromApi

  const action = parseActionPayload(item.diffPreview?.after ?? '')
  const jobType = item.jobType
  const system = jobType.split('.')[0] ?? jobType
  const fields: ApprovalContext['fields'] = []

  if (jobType === 'gmail.send_email') {
    const replyTo = String(action.reply_to ?? action.to ?? '')
    fields.push(
      { label: 'To', value: replyTo || '—' },
      { label: 'Subject', value: String(action.subject || '(thread subject)') },
    )
    if (action.message_id) {
      fields.push({ label: 'Thread / message ID', value: String(action.message_id), mono: true })
    }
  } else {
    for (const [k, v] of Object.entries(action)) {
      if (v != null && String(v).trim()) {
        fields.push({ label: k.replace(/_/g, ' '), value: String(v).slice(0, 500) })
      }
    }
  }

  return {
    system,
    actionLabel: JOB_LABELS[jobType] ?? jobType.replace('.', ' · '),
    summary: item.intentSummary || item.title,
    fields,
    impact: ['Review the technical payload below before approving.'],
    links: [],
    editableKey: jobType === 'gmail.send_email' ? 'body' : 'body',
    editableLabel: jobType === 'gmail.send_email' ? 'Reply message' : 'Message body',
    editableDefault:
      String(action.body ?? '') ||
      (jobType === 'gmail.send_email' ? DEFAULT_GMAIL_REPLY : ''),
    requestedAction: action,
  }
}

export function systemBadgeTone(system: string): 'accent' | 'warn' | 'pass' | 'default' {
  switch (system) {
    case 'gmail':
      return 'accent'
    case 'github':
      return 'default'
    case 'jira':
      return 'warn'
    case 'calendar':
      return 'pass'
    default:
      return 'default'
  }
}

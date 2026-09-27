"""Serialize ORM rows → frontend camelCase shapes (HttpAdapter contract)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aip.db.orm import (
    AgentGuardrailRow,
    AgentRow,
    ApprovalRow,
    AuditEventRow,
    ContextDocumentRow,
    JobRow,
    PolicyRow,
    RunRow,
    ValidationRow,
    WorkspaceRow,
)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def workspace_to_api(row: WorkspaceRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "product": row.product or row.name,
        "description": row.description or "",
        "scope": {
            "repos": list(row.repo_scope or []),
            "jiraKeys": list(row.jira_scope or []),
            "calendars": list(row.calendar_scope or []),
            "emailGroups": list(row.comms_scope or []),
        },
        "createdAt": _iso(row.created_at) or "",
    }


def context_to_api(row: ContextDocumentRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "source": row.source,
        "raw": row.raw,
        "parsedAt": _iso(row.parsed_at),
        "workspaceIds": list(row.workspace_ids or []),
        "parsePreview": row.parse_preview,
    }


def run_to_api(row: RunRow, job_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title or f"Run {row.id[:8]}",
        "status": row.status,
        "objectives": list(row.objectives or []),
        "workspaceIds": list(row.workspace_ids or []),
        "temporalWorkflowId": row.temporal_workflow_id or "",
        "createdAt": _iso(row.created_at) or "",
        "updatedAt": _iso(row.updated_at) or "",
        "jobIds": job_ids if job_ids is not None else [j.id for j in (row.jobs or [])],
    }


def job_to_api(row: JobRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "runId": row.run_id,
        "workspaceId": row.workspace_id,
        "agentId": row.agent_id or "",
        "jobType": row.job_type,
        "title": row.title or row.job_type,
        "status": row.status,
        "requestedAction": dict(row.requested_action or {}),
        "error": row.error,
        "startedAt": _iso(row.started_at),
        "finishedAt": _iso(row.finished_at),
        "validationId": row.validation_id,
        "approvalId": row.approval_id,
        "evidence": row.evidence,
        "idempotencyKey": row.idempotency_key,
    }


def approval_to_api(row: ApprovalRow) -> dict[str, Any]:
    diff = row.diff_preview or {"before": "", "after": ""}
    context = diff.get("context") if isinstance(diff.get("context"), dict) else None
    return {
        "id": row.id,
        "jobId": row.job_id,
        "runId": row.run_id,
        "workspaceId": row.workspace_id,
        "agentId": row.agent_id or "",
        "jobType": row.job_type,
        "title": row.title,
        "intentSummary": row.intent_summary,
        "diffPreview": diff,
        "context": context,
        "decision": row.decision,
        "editedPayload": row.edited_payload,
        "createdAt": _iso(row.created_at) or "",
        "decidedAt": _iso(row.decided_at),
    }


def validation_to_api(row: ValidationRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "jobId": row.job_id,
        "runId": row.run_id,
        "workspaceId": row.workspace_id,
        "agentId": row.agent_id or "",
        "jobType": row.job_type,
        "verdict": row.verdict,
        "confidence": row.confidence,
        "message": row.message,
        "reasoning": row.reasoning,
        "checks": list(row.checks or []),
        "evidence": row.evidence,
        "checkedAt": _iso(row.checked_at) or "",
    }


def guardrail_to_api(row: AgentGuardrailRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "tool": row.tool,
        "mode": row.mode,
        "label": row.label,
        "rationale": row.rationale,
        "source": row.source,
        "createdAt": _iso(row.created_at) or "",
    }


def agent_to_api(row: AgentRow) -> dict[str, Any]:
    origin = dict(row.origin or {})
    specs = dict(row.specs or {})
    return {
        "id": row.id,
        "name": row.name,
        "role": row.role,
        "description": row.description,
        "mission": row.mission,
        "toolScope": list(row.tool_scope or []),
        "workspaceIds": list(row.workspace_ids or []),
        "status": row.status,
        "createdAt": _iso(row.created_at) or "",
        "lastActiveAt": _iso(row.last_active_at) or _iso(row.created_at) or "",
        "origin": {
            "contextDocumentId": origin.get("contextDocumentId", ""),
            "contextDocumentName": origin.get("contextDocumentName", ""),
            "rationale": origin.get("rationale", ""),
            "kgPaths": list(origin.get("kgPaths") or []),
            "signals": list(origin.get("signals") or []),
            "synthesizedAt": origin.get("synthesizedAt") or _iso(row.created_at) or "",
        },
        "specs": {
            "runtime": specs.get("runtime", "openai-agents"),
            "modelHint": specs.get("modelHint", "gpt-4.1-mini"),
            "maxConcurrency": specs.get("maxConcurrency", 2),
            "timeoutSec": specs.get("timeoutSec", 300),
            "memoryKeys": list(specs.get("memoryKeys") or []),
            "inputSchema": list(specs.get("inputSchema") or []),
            "outputSchema": list(specs.get("outputSchema") or []),
            "leastPrivilegeNote": specs.get(
                "leastPrivilegeNote",
                "Tools limited to agent tool_scope and workspace allowlists.",
            ),
        },
        "guardrails": [guardrail_to_api(g) for g in (row.guardrails or [])],
        "activation": row.activation,
        "systemKey": row.system_key,
    }


def policy_group_to_api(workspace_id: str, rows: list[PolicyRow]) -> dict[str, Any]:
    return {
        "workspaceId": workspace_id,
        "actions": [
            {
                "action": p.action,
                "label": p.label or p.action,
                "allowed": p.allowed,
                "hilRequired": p.hil_required,
                "autoMerge": p.auto_merge,
            }
            for p in rows
        ],
    }


def timeline_to_api(row: AuditEventRow) -> dict[str, Any]:
    meta = {str(k): str(v) for k, v in (row.meta or {}).items()}
    return {
        "id": row.id,
        "runId": row.run_id,
        "jobId": row.job_id,
        "kind": row.kind,
        "label": row.label,
        "at": _iso(row.at) or "",
        "meta": meta or None,
    }

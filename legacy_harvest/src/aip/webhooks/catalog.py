"""Versioned Webhook Catalog — inventory of events that can wake agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, select

from aip.persistence.db import get_engine, get_session
from aip.webhooks.models import (
    EnterpriseWebhook,
    WebhookBinding,
    WebhookCatalogVersionRecord,
)


class EnterpriseWebhookRow(SQLModel, table=True):
    id: str = Field(primary_key=True)  # system_id::webhook_id
    connected_system_id: str = Field(index=True)
    catalog_version: int = Field(default=0, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class WebhookCatalogMetaRow(SQLModel, table=True):
    connected_system_id: str = Field(primary_key=True)
    version: int = 0
    last_sync_at: datetime | None = None
    last_reject_reason: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class WebhookBindingRow(SQLModel, table=True):
    id: str = Field(primary_key=True)  # system_id::webhook_id::spec_id
    connected_system_id: str = Field(index=True)
    webhook_id: str = Field(index=True)
    spec_id: str = Field(index=True)
    enabled: bool = True
    reason: str = ""
    company_id: str | None = Field(default=None, index=True)
    project_id: str | None = Field(default=None, index=True)
    scope_level: str = Field(default="project", index=True)


class WebhookDeliveryRow(SQLModel, table=True):
    delivery_id: str = Field(primary_key=True)
    connected_system_id: str = Field(index=True)
    event: str = ""
    action: str = ""
    webhook_id: str = Field(default="", index=True)
    repo: str = ""
    bound: bool = False
    spec_id: str | None = None
    status: str = "received"  # received | queued | ran | skipped | error
    error: str | None = None
    received_at: datetime | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


def _row_id(system_id: str, webhook_id: str, spec_id: str = "") -> str:
    if spec_id:
        return f"{system_id}::{webhook_id}::{spec_id}"
    return f"{system_id}::{webhook_id}"


class WebhookCatalog:
    """Persist webhook inventory + bindings + delivery dedup."""

    def ensure_tables(self) -> None:
        SQLModel.metadata.create_all(get_engine())
        self._migrate_binding_scope_columns()
        self._migrate_binding_primary_key()

    def _migrate_binding_scope_columns(self) -> None:
        """Add company/project/scope columns on existing SQLite tables."""
        engine = get_engine()
        with engine.begin() as conn:
            rows = conn.exec_driver_sql("PRAGMA table_info(webhookbindingrow)").fetchall()
            if not rows:
                return
            existing = {str(row[1]) for row in rows}
            alters = []
            if "company_id" not in existing:
                alters.append(
                    "ALTER TABLE webhookbindingrow ADD COLUMN company_id VARCHAR"
                )
            if "project_id" not in existing:
                alters.append(
                    "ALTER TABLE webhookbindingrow ADD COLUMN project_id VARCHAR"
                )
            if "scope_level" not in existing:
                alters.append(
                    "ALTER TABLE webhookbindingrow ADD COLUMN scope_level VARCHAR DEFAULT 'project'"
                )
            for sql in alters:
                conn.exec_driver_sql(sql)

    def current_version(self, system_id: str) -> int:
        with get_session() as session:
            row = session.get(WebhookCatalogMetaRow, system_id)
            return int(row.version) if row else 0

    def list_webhooks(self, system_id: str | None = None) -> list[EnterpriseWebhook]:
        with get_session() as session:
            stmt = select(EnterpriseWebhookRow)
            if system_id:
                stmt = stmt.where(
                    EnterpriseWebhookRow.connected_system_id == system_id
                )
            rows = session.exec(stmt).all()
            return [EnterpriseWebhook.model_validate(r.payload) for r in rows]

    def accept_discovery(
        self, system_id: str, webhooks: list[EnterpriseWebhook]
    ) -> WebhookCatalogVersionRecord:
        if not webhooks:
            return WebhookCatalogVersionRecord(
                connected_system_id=system_id,
                version=self.current_version(system_id),
                webhook_count=0,
                rejected=True,
                reject_reason="discovery returned zero webhooks",
            )
        ids = [w.id for w in webhooks]
        if len(ids) != len(set(ids)):
            return WebhookCatalogVersionRecord(
                connected_system_id=system_id,
                version=self.current_version(system_id),
                webhook_count=len(self.list_webhooks(system_id)),
                rejected=True,
                reject_reason="duplicate webhook ids",
            )

        now = datetime.now(timezone.utc)
        with get_session() as session:
            meta = session.get(WebhookCatalogMetaRow, system_id)
            new_version = (meta.version if meta else 0) + 1
            existing = session.exec(
                select(EnterpriseWebhookRow).where(
                    EnterpriseWebhookRow.connected_system_id == system_id
                )
            ).all()
            for row in existing:
                session.delete(row)
            for wh in webhooks:
                stamped = wh.model_copy(update={"discovered_at": now})
                session.add(
                    EnterpriseWebhookRow(
                        id=_row_id(system_id, stamped.id),
                        connected_system_id=system_id,
                        catalog_version=new_version,
                        payload=stamped.model_dump(mode="json"),
                    )
                )
            history_entry = {
                "version": new_version,
                "webhook_count": len(webhooks),
                "accepted_at": now.isoformat(),
            }
            if meta is None:
                session.add(
                    WebhookCatalogMetaRow(
                        connected_system_id=system_id,
                        version=new_version,
                        last_sync_at=now,
                        history=[history_entry],
                    )
                )
            else:
                meta.version = new_version
                meta.last_sync_at = now
                hist = list(meta.history or [])
                hist.append(history_entry)
                meta.history = hist[-50:]
                session.add(meta)
            session.commit()
        return WebhookCatalogVersionRecord(
            connected_system_id=system_id,
            version=new_version,
            webhook_count=len(webhooks),
        )

    def seed_github_if_empty(self) -> WebhookCatalogVersionRecord | None:
        self.ensure_tables()
        if self.list_webhooks("github"):
            return None
        from aip.webhooks.github_inventory import github_webhook_seed

        return self.accept_discovery("github", github_webhook_seed())

    def seed_jira_if_empty(self) -> WebhookCatalogVersionRecord | None:
        self.ensure_tables()
        if self.list_webhooks("jira"):
            return None
        from aip.webhooks.jira_inventory import jira_webhook_seed

        return self.accept_discovery("jira", jira_webhook_seed())

    def seed_gmail_if_empty(self) -> WebhookCatalogVersionRecord | None:
        self.ensure_tables()
        if self.list_webhooks("gmail"):
            return None
        from aip.webhooks.gmail_inventory import gmail_webhook_seed

        return self.accept_discovery("gmail", gmail_webhook_seed())

    def list_bindings(self, system_id: str = "github") -> list[WebhookBinding]:
        with get_session() as session:
            rows = session.exec(
                select(WebhookBindingRow).where(
                    WebhookBindingRow.connected_system_id == system_id
                )
            ).all()
            return [
                WebhookBinding(
                    webhook_id=r.webhook_id,
                    connected_system_id=r.connected_system_id,
                    spec_id=r.spec_id,
                    enabled=r.enabled,
                    reason=r.reason,
                    company_id=getattr(r, "company_id", None),
                    project_id=getattr(r, "project_id", None),
                    scope_level=getattr(r, "scope_level", None) or "project",
                )
                for r in rows
            ]

    def upsert_binding(self, binding: WebhookBinding) -> WebhookBinding:
        self.ensure_tables()
        rid = _row_id(
            binding.connected_system_id, binding.webhook_id, binding.spec_id
        )
        with get_session() as session:
            row = session.get(WebhookBindingRow, rid)
            if row is None:
                row = WebhookBindingRow(
                    id=rid,
                    connected_system_id=binding.connected_system_id,
                    webhook_id=binding.webhook_id,
                    spec_id=binding.spec_id,
                    enabled=binding.enabled,
                    reason=binding.reason,
                    company_id=binding.company_id,
                    project_id=binding.project_id,
                    scope_level=binding.scope_level or "project",
                )
            else:
                row.spec_id = binding.spec_id
                row.enabled = binding.enabled
                row.reason = binding.reason
                row.company_id = binding.company_id
                row.project_id = binding.project_id
                row.scope_level = binding.scope_level or "project"
            session.add(row)
            session.commit()
        return binding

    def delete_bindings_for_spec(self, spec_id: str) -> None:
        sid = (spec_id or "").strip()
        if not sid:
            return
        self.ensure_tables()
        with get_session() as session:
            rows = session.exec(
                select(WebhookBindingRow).where(WebhookBindingRow.spec_id == sid)
            ).all()
            for row in rows:
                session.delete(row)
            session.commit()

    def _migrate_binding_primary_key(self) -> None:
        """Rewrite legacy system::webhook_id rows to include spec_id."""
        with get_session() as session:
            rows = list(session.exec(select(WebhookBindingRow)).all())
            if not rows:
                return
            changed = False
            for row in rows:
                expected = _row_id(
                    row.connected_system_id, row.webhook_id, row.spec_id
                )
                if row.id == expected:
                    continue
                session.delete(row)
                session.add(
                    WebhookBindingRow(
                        id=expected,
                        connected_system_id=row.connected_system_id,
                        webhook_id=row.webhook_id,
                        spec_id=row.spec_id,
                        enabled=row.enabled,
                        reason=row.reason,
                        company_id=getattr(row, "company_id", None),
                        project_id=getattr(row, "project_id", None),
                        scope_level=getattr(row, "scope_level", None) or "project",
                    )
                )
                changed = True
            if changed:
                session.commit()

    def find_bindings(
        self,
        system_id: str,
        webhook_id: str,
        *,
        project_id: str | None = None,
        include_company_global: bool = False,
    ) -> list[WebhookBinding]:
        matches = [
            b
            for b in self.list_bindings(system_id)
            if b.enabled and b.webhook_id == webhook_id
        ]
        if project_id is None and not include_company_global:
            out: list[WebhookBinding] = []
            for binding in matches:
                scope = (binding.scope_level or "project").strip().lower()
                if scope == "company":
                    out.append(binding)
                    continue
                # Legacy bindings without project_id remain global until re-synced.
                if not (binding.project_id or "").strip():
                    out.append(binding)
            return out
        out: list[WebhookBinding] = []
        for binding in matches:
            scope = (binding.scope_level or "project").strip().lower()
            if include_company_global and scope == "company":
                out.append(binding)
                continue
            if project_id and binding.project_id == project_id:
                out.append(binding)
                continue
            # Legacy bindings without project_id remain visible until re-synced.
            if project_id and not binding.project_id and scope != "company":
                out.append(binding)
        return out

    def seed_default_github_bindings(self) -> None:
        """PR review / issue / mention defaults (matcher precursor)."""
        from aip.config import settings

        defaults: list[tuple[str, str, str]] = [
            (
                "pull_request.opened",
                settings.github_review_spec_id,
                "default PR code review",
            ),
            (
                "pull_request.synchronize",
                settings.github_review_spec_id,
                "default PR code review on push",
            ),
            (
                "pull_request.reopened",
                settings.github_review_spec_id,
                "default PR code review on reopen",
            ),
            (
                "issues.opened",
                settings.github_issue_spec_id,
                "default issue responder",
            ),
            (
                "issue_comment.created",
                settings.github_mention_spec_id,
                "default mention/comment reply",
            ),
            (
                "pull_request_review_comment.created",
                settings.github_mention_spec_id,
                "default review-comment reply",
            ),
            (
                "workflow_run.completed",
                settings.github_cicd_spec_id,
                "default CI/CD doctor on workflow completion",
            ),
        ]
        for wid, spec_id, reason in defaults:
            self.upsert_binding(
                WebhookBinding(
                    webhook_id=wid,
                    connected_system_id="github",
                    spec_id=(spec_id or "").strip(),
                    enabled=bool((spec_id or "").strip()),
                    reason=reason,
                )
            )

    def seed_default_jira_bindings(self) -> None:
        """Issue triage / comment reply defaults (matcher precursor)."""
        from aip.config import settings

        defaults: list[tuple[str, str, str]] = [
            (
                "jira:issue_created",
                settings.jira_issue_spec_id,
                "default Jira issue triage",
            ),
            (
                "comment_created",
                settings.jira_comment_spec_id,
                "default Jira comment reply",
            ),
        ]
        for wid, spec_id, reason in defaults:
            self.upsert_binding(
                WebhookBinding(
                    webhook_id=wid,
                    connected_system_id="jira",
                    spec_id=(spec_id or "").strip(),
                    enabled=bool((spec_id or "").strip()),
                    reason=reason,
                )
            )

    def has_delivery(self, delivery_id: str) -> bool:
        if not delivery_id:
            return False
        with get_session() as session:
            return session.get(WebhookDeliveryRow, delivery_id) is not None

    def get_delivery(self, delivery_id: str) -> dict[str, Any] | None:
        if not delivery_id:
            return None
        with get_session() as session:
            row = session.get(WebhookDeliveryRow, delivery_id)
            if row is None:
                return None
            return {
                "delivery_id": row.delivery_id,
                "connected_system_id": row.connected_system_id,
                "event": row.event,
                "action": row.action,
                "webhook_id": row.webhook_id,
                "repo": row.repo,
                "bound": row.bound,
                "spec_id": row.spec_id,
                "status": row.status,
                "error": row.error,
                "payload_summary": row.payload_summary or {},
            }

    def record_delivery(
        self,
        *,
        delivery_id: str,
        connected_system_id: str,
        event: str,
        action: str,
        webhook_id: str,
        repo: str,
        bound: bool,
        spec_id: str | None,
        status: str,
        error: str | None = None,
        payload_summary: dict[str, Any] | None = None,
    ) -> None:
        self.ensure_tables()
        with get_session() as session:
            existing = session.get(WebhookDeliveryRow, delivery_id)
            if existing is not None:
                return
            session.add(
                WebhookDeliveryRow(
                    delivery_id=delivery_id,
                    connected_system_id=connected_system_id,
                    event=event,
                    action=action,
                    webhook_id=webhook_id,
                    repo=repo,
                    bound=bound,
                    spec_id=spec_id,
                    status=status,
                    error=error,
                    received_at=datetime.now(timezone.utc),
                    payload_summary=payload_summary or {},
                )
            )
            session.commit()

    def update_delivery_status(
        self,
        delivery_id: str,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        if not delivery_id:
            return
        with get_session() as session:
            row = session.get(WebhookDeliveryRow, delivery_id)
            if row is None:
                return
            row.status = status
            if error is not None:
                row.error = error
            session.add(row)
            session.commit()

    def record_spec_result(
        self,
        delivery_id: str,
        *,
        spec_id: str,
        status: str,
        error: str | None = None,
        expected_spec_ids: list[str] | None = None,
    ) -> str:
        """Merge per-spec outcome and roll up top-level delivery status.

        Returns the recomputed top-level status.
        """
        if not delivery_id or not (spec_id or "").strip():
            return ""
        spec_id = spec_id.strip()
        status = (status or "").strip().lower()
        with get_session() as session:
            row = session.get(WebhookDeliveryRow, delivery_id)
            if row is None:
                return ""
            summary = dict(row.payload_summary or {})
            results = dict(summary.get("spec_results") or {})
            entry: dict[str, Any] = {"status": status}
            if error:
                entry["error"] = str(error)[:400]
            results[spec_id] = entry
            summary["spec_results"] = results
            expected = list(expected_spec_ids or summary.get("spec_ids") or [])
            if expected and set(expected) <= set(results.keys()):
                statuses = [str(results[s].get("status") or "") for s in expected]
                complete = True
            else:
                statuses = [str(v.get("status") or "") for v in results.values()]
                complete = not expected

            if any(s == "error" for s in statuses):
                rolled = "error"
                err_parts = [
                    f"{sid}:{results[sid].get('error')}"
                    for sid in (expected or list(results.keys()))
                    if sid in results
                    and str(results[sid].get("status")) == "error"
                    and results[sid].get("error")
                ]
                row.error = ("; ".join(err_parts) or error or row.error or "")[:500]
            elif not complete:
                rolled = "queued"
            elif statuses and all(s == "skipped" for s in statuses):
                rolled = "skipped"
                row.error = None
            elif any(s == "handled" for s in statuses):
                rolled = "handled"
                row.error = None
            else:
                rolled = "queued"

            row.status = rolled
            row.payload_summary = summary
            session.add(row)
            session.commit()
            return rolled

    def list_deliveries(
        self, system_id: str = "github", *, limit: int = 40
    ) -> list[dict[str, Any]]:
        from sqlalchemy import desc

        with get_session() as session:
            rows = session.exec(
                select(WebhookDeliveryRow)
                .where(WebhookDeliveryRow.connected_system_id == system_id)
                .order_by(desc(WebhookDeliveryRow.received_at))
                .limit(limit)
            ).all()
            out = []
            for r in rows:
                out.append(
                    {
                        "delivery_id": r.delivery_id,
                        "event": r.event,
                        "action": r.action,
                        "webhook_id": r.webhook_id,
                        "repo": r.repo,
                        "bound": r.bound,
                        "spec_id": r.spec_id,
                        "status": r.status,
                        "error": r.error,
                        "received_at": r.received_at.isoformat()
                        if r.received_at
                        else None,
                    }
                )
            return out

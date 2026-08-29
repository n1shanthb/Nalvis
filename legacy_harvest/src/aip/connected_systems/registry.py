"""Persisted MCP / Connected System registry — admin-managed, matcher later."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, select

from aip.connected_systems.models import (
    ConnectionStatus,
    HealthStatus,
    TransportKind,
)
from aip.persistence.db import get_engine, get_session


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not cleaned:
        raise ValueError("id is empty")
    return cleaned[:64]


# MVP Connected Systems only (GitHub, Gmail, Calendar, Jira).
BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "github",
        "display_name": "GitHub",
        "provider": "github",
        "mcp_url": "https://api.githubcopilot.com/mcp/",
        "toolsets": "pull_requests,repos,issues,actions",
        "description": "GitHub remote MCP (PRs, repos, issues, Actions)",
        "auth_mode": "github_app",
    },
    {
        "id": "gmail",
        "display_name": "Gmail",
        "provider": "gmail",
        "mcp_url": "",
        "toolsets": "email",
        "description": "Gmail native REST (cataloged like MCP; send/search/reply)",
        "auth_mode": "gmail_oauth",
        "transport": TransportKind.NATIVE.value,
    },
    {
        "id": "calendar",
        "display_name": "Google Calendar",
        "provider": "calendar",
        "mcp_url": "",
        "toolsets": "calendar",
        "description": "Google Calendar native REST (reuses Gmail OAuth; add Calendar scopes)",
        "auth_mode": "gmail_oauth",
        "transport": TransportKind.NATIVE.value,
    },
    {
        "id": "jira",
        "display_name": "Jira",
        "provider": "jira",
        "mcp_url": "https://mcp.atlassian.com/v1/mcp",
        "toolsets": "jira",
        "description": "Atlassian Rovo MCP (Jira issues, JQL, comments) — Bearer service account token",
        "auth_mode": "bearer",
    },
]

MVP_SYSTEM_IDS = frozenset(p["id"] for p in BUILTIN_PRESETS)


class McpServerRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    display_name: str
    provider: str = "generic"
    mcp_url: str = ""
    toolsets: str = ""
    description: str = ""
    auth_mode: str = "bearer"  # bearer | github_app | none
    bearer_token: str = ""  # optional; prefer env in production
    status: str = ConnectionStatus.DISCONNECTED.value
    health: str = HealthStatus.UNKNOWN.value
    transport: str = TransportKind.MCP_STREAMABLE_HTTP.value
    builtin: bool = False
    last_error: str | None = None
    last_sync_at: datetime | None = None
    configuration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class McpRegistry:
    """Global admin registry for MCP Connected Systems."""

    def ensure_tables(self) -> None:
        SQLModel.metadata.create_all(get_engine())
        self.seed_builtins()

    def seed_builtins(self) -> None:
        with get_session() as session:
            for preset in BUILTIN_PRESETS:
                existing = session.get(McpServerRow, preset["id"])
                if existing is not None:
                    # Upsert Gmail native preset when leftover MCP placeholder exists.
                    if preset["id"] == "gmail" and (
                        existing.auth_mode != "gmail_oauth"
                        or existing.transport != TransportKind.NATIVE.value
                        or not (existing.description or "").startswith("Gmail native")
                    ):
                        existing.display_name = preset["display_name"]
                        existing.provider = preset["provider"]
                        existing.mcp_url = ""
                        existing.toolsets = preset.get("toolsets") or "email"
                        existing.description = preset.get("description") or ""
                        existing.auth_mode = "gmail_oauth"
                        existing.transport = TransportKind.NATIVE.value
                        existing.builtin = True
                        session.add(existing)
                    elif preset["id"] == "calendar" and (
                        existing.auth_mode != "gmail_oauth"
                        or existing.transport != TransportKind.NATIVE.value
                        or existing.provider != "calendar"
                    ):
                        existing.display_name = preset["display_name"]
                        existing.provider = "calendar"
                        existing.mcp_url = ""
                        existing.toolsets = preset.get("toolsets") or "calendar"
                        existing.description = preset.get("description") or ""
                        existing.auth_mode = "gmail_oauth"
                        existing.transport = TransportKind.NATIVE.value
                        existing.builtin = True
                        session.add(existing)
                    elif preset["id"] == "jira":
                        wanted_url = (
                            preset.get("mcp_url") or "https://mcp.atlassian.com/v1/mcp"
                        )
                        if (
                            (existing.mcp_url or "").strip() != wanted_url
                            or existing.provider != "jira"
                            or not (existing.description or "").startswith("Atlassian")
                        ):
                            existing.display_name = preset["display_name"]
                            existing.provider = "jira"
                            existing.mcp_url = wanted_url
                            existing.toolsets = preset.get("toolsets") or "jira"
                            existing.description = preset.get("description") or ""
                            existing.auth_mode = "bearer"
                            existing.transport = TransportKind.MCP_STREAMABLE_HTTP.value
                            existing.builtin = True
                            session.add(existing)
                    elif preset["id"] == "github":
                        wanted = preset.get("toolsets") or (
                            "pull_requests,repos,issues,actions"
                        )
                        if (existing.toolsets or "").strip() != wanted:
                            existing.toolsets = wanted
                            existing.description = (
                                preset.get("description") or existing.description
                            )
                            session.add(existing)
                    continue
                session.add(
                    McpServerRow(
                        id=preset["id"],
                        display_name=preset["display_name"],
                        provider=preset["provider"],
                        mcp_url=preset.get("mcp_url") or "",
                        toolsets=preset.get("toolsets") or "",
                        description=preset.get("description") or "",
                        auth_mode=preset.get("auth_mode") or "bearer",
                        transport=preset.get("transport")
                        or TransportKind.MCP_STREAMABLE_HTTP.value,
                        builtin=True,
                    )
                )
            # Drop non-MVP rows (old placeholders + custom demos).
            for row in session.exec(select(McpServerRow)).all():
                if row.id not in MVP_SYSTEM_IDS:
                    session.delete(row)
            session.commit()

    def list(self) -> list[McpServerRow]:
        with get_session() as session:
            rows = session.exec(select(McpServerRow).order_by(McpServerRow.display_name)).all()
            return list(rows)

    def get(self, system_id: str) -> McpServerRow | None:
        with get_session() as session:
            return session.get(McpServerRow, system_id)

    def add(
        self,
        *,
        system_id: str,
        display_name: str,
        mcp_url: str = "",
        toolsets: str = "",
        description: str = "",
        auth_mode: str = "bearer",
        bearer_token: str = "",
        provider: str | None = None,
    ) -> McpServerRow:
        sid = _slug(system_id)
        with get_session() as session:
            if session.get(McpServerRow, sid) is not None:
                raise ValueError(f"MCP id already exists: {sid}")
            row = McpServerRow(
                id=sid,
                display_name=(display_name or sid).strip(),
                provider=(provider or sid).strip(),
                mcp_url=(mcp_url or "").strip(),
                toolsets=(toolsets or "").strip(),
                description=(description or "").strip(),
                auth_mode=(auth_mode or "bearer").strip(),
                bearer_token=(bearer_token or "").strip(),
                builtin=False,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def update(
        self,
        system_id: str,
        *,
        display_name: str | None = None,
        mcp_url: str | None = None,
        toolsets: str | None = None,
        description: str | None = None,
        auth_mode: str | None = None,
        bearer_token: str | None = None,
    ) -> McpServerRow:
        with get_session() as session:
            row = session.get(McpServerRow, system_id)
            if row is None:
                raise KeyError(system_id)
            if display_name is not None:
                row.display_name = display_name.strip()
            if mcp_url is not None:
                row.mcp_url = mcp_url.strip()
            if toolsets is not None:
                row.toolsets = toolsets.strip()
            if description is not None:
                row.description = description.strip()
            if auth_mode is not None:
                row.auth_mode = auth_mode.strip()
            if bearer_token is not None and bearer_token.strip():
                row.bearer_token = bearer_token.strip()
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def set_runtime_state(
        self,
        system_id: str,
        *,
        status: str | None = None,
        health: str | None = None,
        last_error: str | None = None,
        last_sync_at: datetime | None = None,
        clear_error: bool = False,
    ) -> McpServerRow:
        with get_session() as session:
            row = session.get(McpServerRow, system_id)
            if row is None:
                raise KeyError(system_id)
            if status is not None:
                row.status = status
            if health is not None:
                row.health = health
            if clear_error:
                row.last_error = None
            elif last_error is not None:
                row.last_error = last_error
            if last_sync_at is not None:
                row.last_sync_at = last_sync_at
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def delete(self, system_id: str) -> None:
        with get_session() as session:
            row = session.get(McpServerRow, system_id)
            if row is None:
                return
            if row.builtin:
                raise ValueError("Cannot delete builtin MCP presets — clear URL instead")
            session.delete(row)
            session.commit()

    def summary(self) -> dict[str, int]:
        from aip.integrations.gmail_oauth import gmail_configured

        rows = self.list()
        connected = sum(1 for r in rows if r.status == ConnectionStatus.CONNECTED.value)
        configured = 0
        for r in rows:
            if r.id == "github" or (r.mcp_url or "").strip():
                configured += 1
            elif r.id in {"gmail", "calendar"} or r.auth_mode == "gmail_oauth":
                if gmail_configured():
                    configured += 1
        return {
            "total": len(rows),
            "connected": connected,
            "configured": configured,
            "placeholders": len(rows) - configured,
        }

"""Connector client interfaces (MCP GitHub/Jira; native Gmail/Calendar)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GitHubConnector(Protocol):
    def list_issue_comments(self, *, owner: str, repo: str, number: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class JiraConnector(Protocol):
    def get_issue(self, issue_key: str) -> dict[str, Any]: ...


@runtime_checkable
class GmailConnector(Protocol):
    def fetch_email(self, message_id: str) -> dict[str, Any]: ...

    def send_email(self, *, to: str, subject: str, body: str) -> dict[str, Any]: ...


@runtime_checkable
class CalendarConnector(Protocol):
    def create_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...


__all__ = [
    "CalendarConnector",
    "GmailConnector",
    "GitHubConnector",
    "JiraConnector",
]

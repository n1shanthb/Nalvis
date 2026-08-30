"""Minimal settings for portable_core connectors (no app_context / DB)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GitHub
    github_token: str = ""
    github_app_id: str = ""
    github_app_installation_id: str = ""
    github_app_private_key: str = ""
    github_app_private_key_path: str = ""
    connected_system_github_mcp_enabled: bool = True
    connected_system_github_mcp_url: str = "https://api.githubcopilot.com/mcp/"
    connected_system_github_mcp_toolsets: str = "pull_requests,repos,issues,actions"

    # Jira / Atlassian
    connected_system_jira_mcp_enabled: bool = True
    connected_system_jira_mcp_url: str = "https://mcp.atlassian.com/v1/mcp"
    atlassian_mcp_token: str = ""
    jira_mcp_token: str = ""
    atlassian_email: str = ""
    atlassian_cloud_id: str = ""

    # Gmail / Calendar (native)
    connected_system_gmail_enabled: bool = True
    connected_system_calendar_enabled: bool = True
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_user: str = ""
    gmail_pubsub_topic: str = ""
    gmail_watch_label_ids: str = "INBOX"
    gmail_watch_renew_hours: int = 12

    # Demo / offline
    offline_demo_mode: bool = True

    # LLM (OpenAI-compatible: OpenAI or OpenRouter)
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    llm_api_base: str = ""
    openai_model: str = ""
    llm_model: str = ""

    # API / tunnel
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    generated_dir: str = "data/generated"
    github_webhook_secret: str = ""
    jira_webhook_secret: str = ""
    gmail_webhook_secret: str = ""

    # Smoke targets (optional; GitHub smoke must use analytics-resume only)
    smoke_github_owner: str = "n1shanthb"
    smoke_github_repo: str = "analytics-resume"
    # Secondary repo where GitHub App is installed for PR/CI writes (owner/repo)
    smoke_github_app_repo: str = ""
    smoke_jira_project_key: str = ""

    # Data plane / orchestration (Authority: Postgres + Redis + Temporal)
    database_url: str = "postgresql+asyncpg://agentsuite:agentsuite@127.0.0.1:5432/agentsuite"
    database_url_sync: str = "postgresql://agentsuite:agentsuite@127.0.0.1:5432/agentsuite"
    redis_url: str = "redis://127.0.0.1:6379/0"
    temporal_host: str = "127.0.0.1:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "agentsuite-main"


settings = Settings()


def generated_path() -> Path:
    path = Path(settings.generated_dir)
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path

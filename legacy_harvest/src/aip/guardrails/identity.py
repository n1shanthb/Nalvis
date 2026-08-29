"""Agent Execution Identity context."""

from __future__ import annotations

import contextvars
from pydantic import BaseModel

class AgentExecutionIdentity(BaseModel):
    agent_id: str
    execution_id: str
    project_id: str
    organization_id: str
    environment: str

_execution_identity_var: contextvars.ContextVar[AgentExecutionIdentity | None] = contextvars.ContextVar(
    "execution_identity", default=None
)
_gmail_run_context_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "gmail_run_context", default=None
)

def get_execution_identity() -> AgentExecutionIdentity | None:
    return _execution_identity_var.get()

def set_execution_identity(identity: AgentExecutionIdentity) -> contextvars.Token:
    return _execution_identity_var.set(identity)

def reset_execution_identity(token: contextvars.Token) -> None:
    _execution_identity_var.reset(token)


def get_gmail_run_context() -> dict | None:
    return _gmail_run_context_var.get()


def set_gmail_run_context(context: dict | None) -> contextvars.Token:
    return _gmail_run_context_var.set(context)


def reset_gmail_run_context(token: contextvars.Token) -> None:
    _gmail_run_context_var.reset(token)

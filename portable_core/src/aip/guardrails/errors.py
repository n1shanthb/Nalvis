"""Guardrail specific errors."""

class GuardrailEnforcementError(Exception):
    """Raised when an external tool execution is blocked by a guardrail policy."""
    pass

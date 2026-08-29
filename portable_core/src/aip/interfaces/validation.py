"""Stable validation interfaces for the clean rebuild."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from aip.validation.models import ValidationRecord
from aip.validation.verdicts import AuthorityVerdict, to_authority_verdict


@runtime_checkable
class Validator(Protocol):
    def validate(self, **kwargs: Any) -> ValidationRecord: ...


__all__ = [
    "AuthorityVerdict",
    "ValidationRecord",
    "Validator",
    "to_authority_verdict",
]

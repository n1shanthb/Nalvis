"""Map legacy validation verdicts to AUTHORITY.md PASS / FAIL / NO_EVIDENCE."""

from __future__ import annotations

from typing import Literal

AuthorityVerdict = Literal["PASS", "FAIL", "NO_EVIDENCE"]

_LEGACY_TO_AUTHORITY: dict[str, AuthorityVerdict] = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "INSUFFICIENT_EVIDENCE": "NO_EVIDENCE",
    "ERROR": "FAIL",
    "PARTIAL": "FAIL",
    "REVIEW": "NO_EVIDENCE",
    "NOT_APPLICABLE": "NO_EVIDENCE",
}


def to_authority_verdict(legacy: str | None) -> AuthorityVerdict:
    """Normalize any legacy verdict string to the public Authority trio."""
    key = (legacy or "").strip().upper()
    if not key:
        return "NO_EVIDENCE"
    return _LEGACY_TO_AUTHORITY.get(key, "NO_EVIDENCE")


def from_check_outcome(outcome: str | None) -> AuthorityVerdict:
    """Map a single check outcome (e.g. from verify_*) to Authority."""
    return to_authority_verdict(outcome)

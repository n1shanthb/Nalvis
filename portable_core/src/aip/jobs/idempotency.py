"""Idempotency key helpers for external write jobs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_idempotency_key(
    *,
    run_id: str,
    workspace_id: str,
    job_type: str,
    requested_action: dict[str, Any],
    salt: str = "",
) -> str:
    payload = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "job_type": job_type,
        "action": requested_action,
        "salt": salt,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode()).hexdigest()[:32]
    return f"{job_type}:{digest}"

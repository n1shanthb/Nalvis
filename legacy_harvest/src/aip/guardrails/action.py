import hashlib
import json
from typing import Any

def canonical_action_hash(
    execution_id: str,
    agent_id: str,
    project_id: str,
    tool: str,
    arguments: dict[str, Any],
    policy_version: str | None = None,
) -> str:
    """Create a deterministic SHA-256 hash for an exact action."""
    # Deterministic serialization: sort keys, strip whitespace, strict encode
    canonical_repr = {
        "execution_id": execution_id,
        "agent_id": agent_id,
        "project_id": project_id,
        "tool": tool,
        "arguments": arguments,
        "policy_version": policy_version,
    }
    
    serialized = json.dumps(
        canonical_repr,
        sort_keys=True,
        separators=(',', ':')
    ).encode('utf-8')
    
    return hashlib.sha256(serialized).hexdigest()

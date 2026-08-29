"""Extract portable_core from legacy_harvest (Phase 0A)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "legacy_harvest" / "src" / "aip"
DST = ROOT / "portable_core" / "src" / "aip"

ACCEPT = [
    "contracts/__init__.py",
    "contracts/capability_webhooks.py",
    "contracts/graph.py",
    "contracts/llm.py",
    "contracts/models.py",
    "contracts/runtime.py",
    "contracts/spec_validation.py",
    "contracts/spec_version.py",
    "contracts/specification.py",
    "contracts/tools.py",
    "guardrails/__init__.py",
    "guardrails/action.py",
    "guardrails/decisions.py",
    "guardrails/engine.py",
    "guardrails/errors.py",
    "guardrails/identity.py",
    "guardrails/models.py",
    "validation/claims.py",
    "webhooks/__init__.py",
    "webhooks/models.py",
    "webhooks/github_inventory.py",
    "webhooks/gmail_inventory.py",
    "webhooks/jira_inventory.py",
    "webhooks/match.py",
    "integrations/__init__.py",
    "integrations/github_app.py",
    "integrations/gmail_oauth.py",
    "tools/calendar.py",
    "connected_systems/providers/github.py",
    "connected_systems/providers/calendar.py",
    "connected_systems/providers/generic_mcp.py",
]


def main() -> None:
    if DST.parent.exists():
        shutil.rmtree(DST.parent)
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "__init__.py").write_text(
        '"""Portable AIP core — Phase 0A extraction."""\n\n__version__ = "0.1.0-portable"\n',
        encoding="utf-8",
    )

    copied: list[str] = []
    for rel in ACCEPT:
        s = SRC / rel
        d = DST / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        copied.append(rel)

    packages = [
        "connected_systems",
        "connected_systems/providers",
        "tools",
        "validation",
        "interfaces",
    ]
    for pkg in packages:
        p = DST / pkg
        p.mkdir(parents=True, exist_ok=True)
        init = p / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")

    (DST / "connected_systems" / "__init__.py").write_text(
        '"""Connected systems — portable presets and providers."""\n',
        encoding="utf-8",
    )
    (DST / "connected_systems" / "providers" / "__init__.py").write_text(
        '"""Provider modules: github, jira, calendar, generic_mcp."""\n',
        encoding="utf-8",
    )
    (DST / "validation" / "__init__.py").write_text(
        '"""Validation core — evidence, claims, verifiers, verdict mapping."""\n',
        encoding="utf-8",
    )
    (DST / "tools" / "__init__.py").write_text(
        '"""Native tool wrappers (Gmail/Calendar)."""\n',
        encoding="utf-8",
    )
    (DST / "interfaces" / "__init__.py").write_text(
        '"""Stable portable interfaces for the clean rebuild."""\n',
        encoding="utf-8",
    )

    report = {"copied_as_is": copied, "count": len(copied)}
    (ROOT / "portable_core" / "CLASSIFICATION.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(f"copied {len(copied)} files to {DST}")


if __name__ == "__main__":
    main()

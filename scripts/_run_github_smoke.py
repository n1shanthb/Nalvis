"""Run GitHub MCP smoke with defaults."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SMOKE_GITHUB_OWNER", "n1shanthb")
os.environ.setdefault("SMOKE_GITHUB_REPO", "analytics-resume")

from aip.connectors.smoke import smoke_github, smoke_github_mcp_list  # noqa: E402

out = {
    "github_mcp_list": smoke_github_mcp_list(),
    "github_write": smoke_github(),
}
print(json.dumps(out, indent=2, default=str)[:4000])
print("OK" if out["github_write"].get("ok") and out["github_mcp_list"].get("ok") else "FAIL")

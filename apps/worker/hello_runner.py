"""Run HelloWorkflow once against local Temporal (Phase 0 DoD)."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

from temporalio.client import Client

from aip.config import settings
from apps.worker.workflows.hello import HelloWorkflow


async def main() -> int:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )
    workflow_id = f"hello-{uuid.uuid4().hex[:8]}"
    result = await client.execute_workflow(
        HelloWorkflow.run,
        "agentsuite",
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    print({"workflow_id": workflow_id, "result": result})
    ok = result == "hello, agentsuite"
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

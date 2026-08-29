"""Temporal worker process for Agentsuite task queues."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from aip.config import settings
from aip.db.schema import init_db
from aip.orchestration import get_activities, get_workflows
from apps.worker.workflows.hello import HelloWorkflow, hello_activity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentsuite.worker")


async def run_worker() -> None:
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("init_db failed (will retry in activities): %s", exc)

    workflows = get_workflows()
    activities = get_activities()

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[*workflows, HelloWorkflow],
        activities=[*activities, hello_activity],
    )
    logger.info(
        "worker listening queue=%s host=%s namespace=%s workflows=%s",
        settings.temporal_task_queue,
        settings.temporal_host,
        settings.temporal_namespace,
        [w.__name__ for w in workflows],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

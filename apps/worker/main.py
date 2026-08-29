"""Temporal worker process for Agentsuite task queues."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from aip.config import settings
from apps.worker.workflows.hello import HelloWorkflow, hello_activity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentsuite.worker")


async def run_worker() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow],
        activities=[hello_activity],
    )
    logger.info(
        "worker listening queue=%s host=%s namespace=%s",
        settings.temporal_task_queue,
        settings.temporal_host,
        settings.temporal_namespace,
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

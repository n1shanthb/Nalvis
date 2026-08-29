"""Hello Temporal workflow — Phase 0 connectivity proof."""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow


@activity.defn(name="hello_activity")
async def hello_activity(name: str) -> str:
    return f"hello, {name}"


@workflow.defn(name="HelloWorkflow")
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str = "agentsuite") -> str:
        return await workflow.execute_activity(
            hello_activity,
            name,
            start_to_close_timeout=timedelta(seconds=30),
        )

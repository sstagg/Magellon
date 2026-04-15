"""CtfWorkflow — single-activity workflow for the CTF plugin.

The workflow body is deliberately tiny: dispatch one activity by name on
the plugin's canonical task queue, surface its output. All compute
lives in the plugin worker; the workflow exists so the host can drive
CTF jobs through Temporal (retries, timeouts, history) instead of a
bare RabbitMQ message.

The activity and queue names are the SDK's canonical scheme (see
``magellon_sdk.worker.runtime``) — host and worker must agree without
negotiation. They are pinned as module constants rather than computed
so Temporal's workflow sandbox doesn't need to trace PluginBase.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from magellon_sdk.worker.types import PluginActivityInput, PluginActivityOutput


CTF_PLUGIN_ID = "ctf/ctffind"
CTF_ACTIVITY_NAME = "plugin.ctf/ctffind.run"
CTF_TASK_QUEUE = "magellon.ctf/ctffind"
CTF_WORKFLOW_NAME = "magellon.ctf.CtfWorkflow"


@workflow.defn(name=CTF_WORKFLOW_NAME)
class CtfWorkflow:
    """Run the CTF plugin once. Input/output are the SDK wire types."""

    @workflow.run
    async def run(self, payload: PluginActivityInput) -> Dict[str, Any]:
        result: PluginActivityOutput = await workflow.execute_activity(
            CTF_ACTIVITY_NAME,
            payload,
            task_queue=CTF_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=3,
                backoff_coefficient=2.0,
            ),
        )
        return result.output


__all__ = [
    "CTF_ACTIVITY_NAME",
    "CTF_PLUGIN_ID",
    "CTF_TASK_QUEUE",
    "CTF_WORKFLOW_NAME",
    "CtfWorkflow",
]

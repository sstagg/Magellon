"""Tests for CtfWorkflow (Phase 2 PR 2.3).

Two layers:

1. Structure tests (always run) — pin the workflow name, activity name,
   task queue, and that imports survive the Temporal workflow sandbox.
   These are characterization-style: if they fail, a contract that the
   host or the CTF plugin worker relies on has drifted.

2. End-to-end test (opt-in) — boots an in-process Worker that registers
   CtfWorkflow + a fake CTF activity, starts the workflow via a Temporal
   client, and asserts the output round-trips. Skipped unless
   ``TEMPORAL_TEST_SERVER=1`` is set, because the test-server download
   is flaky on Windows CI runners.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from workflows.ctf_workflow import (
    CTF_ACTIVITY_NAME,
    CTF_PLUGIN_ID,
    CTF_TASK_QUEUE,
    CTF_WORKFLOW_NAME,
    CtfWorkflow,
)


# ---------------------------------------------------------------------------
# Structure / contract tests
# ---------------------------------------------------------------------------


def test_workflow_name_matches_decorator():
    """The registered workflow name must match the published constant —
    host code starts workflows by name and that string is a contract."""
    assert CtfWorkflow.__temporal_workflow_definition.name == CTF_WORKFLOW_NAME


def test_activity_name_matches_sdk_scheme():
    """Activity name must follow the SDK's ``plugin.<category>/<name>.run``
    scheme so the CTF plugin worker (which names its activity the same
    way from PluginInfo) is reachable."""
    assert CTF_ACTIVITY_NAME == f"plugin.{CTF_PLUGIN_ID}.run"


def test_task_queue_matches_sdk_scheme():
    """Queue name must follow the SDK's ``magellon.<category>/<name>``
    scheme — the worker binds to this queue via plugin_task_queue()."""
    assert CTF_TASK_QUEUE == f"magellon.{CTF_PLUGIN_ID}"


def test_workflow_queue_agrees_with_sdk_helper():
    """Prove the hard-coded constant equals what the SDK helper returns
    for a CTF-shaped plugin. If the SDK naming scheme ever changes, this
    test fails loudly instead of silently drifting."""
    from typing import Type

    from pydantic import BaseModel

    from magellon_sdk.base import PluginBase
    from magellon_sdk.models import PluginInfo, TaskCategory
    from magellon_sdk.progress import NullReporter, ProgressReporter
    from magellon_sdk.worker import plugin_task_queue

    class _Inp(BaseModel):
        pass

    class _Out(BaseModel):
        pass

    class _FakeCtf(PluginBase[_Inp, _Out]):
        task_category = TaskCategory(code=1, name="ctf", description="")

        def get_info(self):
            return PluginInfo(name="ctffind", version="0")

        @classmethod
        def input_schema(cls) -> Type[_Inp]:
            return _Inp

        @classmethod
        def output_schema(cls) -> Type[_Out]:
            return _Out

        def execute(self, input_data, *, reporter: ProgressReporter = NullReporter()):
            return _Out()

    assert plugin_task_queue(_FakeCtf()) == CTF_TASK_QUEUE


# ---------------------------------------------------------------------------
# End-to-end test (opt-in)
# ---------------------------------------------------------------------------


_SKIP_E2E = os.environ.get("TEMPORAL_TEST_SERVER") != "1"


@pytest.mark.skipif(
    _SKIP_E2E,
    reason="Set TEMPORAL_TEST_SERVER=1 to exercise CtfWorkflow against the "
    "Temporalite test server (downloads a binary on first run).",
)
def test_ctf_workflow_end_to_end():
    """Drive CtfWorkflow through a real workflow runner.

    We register a fake activity under the real CTF activity name so the
    workflow's dispatch path is exercised without needing the ctffind
    binary or a live plugin container.
    """
    import temporalio.activity as activity
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Worker

    from magellon_sdk.worker.types import PluginActivityInput, PluginActivityOutput

    @activity.defn(name=CTF_ACTIVITY_NAME)
    async def fake_ctffind(payload: PluginActivityInput) -> PluginActivityOutput:
        return PluginActivityOutput(output={"defocus": 1.23, "echo": payload.input})

    async def _run() -> dict:
        async with await WorkflowEnvironment.start_local() as env:
            client: Client = env.client
            async with Worker(
                client,
                task_queue=CTF_TASK_QUEUE,
                workflows=[CtfWorkflow],
                activities=[fake_ctffind],
            ):
                return await client.execute_workflow(
                    CtfWorkflow.run,
                    PluginActivityInput(plugin_id=CTF_PLUGIN_ID, input={"hello": "world"}),
                    id=f"ctf-test-{uuid.uuid4()}",
                    task_queue=CTF_TASK_QUEUE,
                )

    result = asyncio.run(_run())
    assert result == {"defocus": 1.23, "echo": {"hello": "world"}}

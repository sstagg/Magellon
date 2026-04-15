"""Worker runtime tests for PR 2.1.

Scope: the activity scaffold — ``build_plugin_activity`` + queue naming.
Uses ``temporalio.testing.ActivityEnvironment`` so we exercise a real
Temporal activity harness in-process, no server download required.

End-to-end workflow-level tests land in PR 2.3 (``CtfWorkflow``) where
the dev stack's Temporal server (added in PR 0.9) is the natural host.
"""
from __future__ import annotations

from typing import Type

import pytest
from pydantic import BaseModel
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from magellon_sdk.base import PluginBase
from magellon_sdk.models import PluginInfo, TaskCategory
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.worker import build_plugin_activity, plugin_task_queue
from magellon_sdk.worker.types import PluginActivityInput, PluginActivityOutput


# ---------------------------------------------------------------------------
# A minimal plugin used only for this test.
# ---------------------------------------------------------------------------


class DoublerInput(BaseModel):
    n: int


class DoublerOutput(BaseModel):
    doubled: int


class DoublerPlugin(PluginBase[DoublerInput, DoublerOutput]):
    task_category = TaskCategory(code=999, name="test", description="test")

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="doubler", version="0.1", schema_version="1")

    @classmethod
    def input_schema(cls) -> Type[DoublerInput]:
        return DoublerInput

    @classmethod
    def output_schema(cls) -> Type[DoublerOutput]:
        return DoublerOutput

    def execute(
        self,
        input_data: DoublerInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> DoublerOutput:
        reporter.report(50, "halfway")
        return DoublerOutput(doubled=input_data.n * 2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_plugin_task_queue_is_deterministic():
    """Host and plugin must agree on the queue name without negotiation."""
    plugin = DoublerPlugin()
    assert plugin_task_queue(plugin) == "magellon.test/doubler"


def test_activity_name_is_deterministic():
    """Workflows dispatch by activity name — pin the naming scheme."""
    activity = build_plugin_activity(DoublerPlugin())
    # Temporal stamps the name onto the decorated callable.
    assert activity.__temporal_activity_definition.name == "plugin.test/doubler.run"


@pytest.mark.asyncio
async def test_activity_runs_plugin_end_to_end():
    plugin = DoublerPlugin()
    activity = build_plugin_activity(plugin)

    env = ActivityEnvironment()
    payload = PluginActivityInput(plugin_id="test/doubler", input={"n": 21})
    result: PluginActivityOutput = await env.run(activity, payload)

    assert result.output == {"doubled": 42}


@pytest.mark.asyncio
async def test_activity_surfaces_plugin_exception():
    """Plugin errors must propagate as Temporal failures — the host
    decides retry policy at the workflow layer, not silently swallowed
    by the activity wrapper."""

    class BrokenPlugin(DoublerPlugin):
        def execute(self, input_data, *, reporter=NullReporter()):
            raise RuntimeError("boom")

    activity = build_plugin_activity(BrokenPlugin())
    env = ActivityEnvironment()

    with pytest.raises((RuntimeError, ApplicationError)) as exc_info:
        await env.run(
            activity,
            PluginActivityInput(plugin_id="test/doubler", input={"n": 1}),
        )
    assert "boom" in str(exc_info.value)


@pytest.mark.asyncio
async def test_activity_validates_input_via_plugin():
    """Activity delegates validation to the plugin — bad input raises."""

    activity = build_plugin_activity(DoublerPlugin())
    env = ActivityEnvironment()

    with pytest.raises(Exception):
        await env.run(
            activity,
            PluginActivityInput(plugin_id="test/doubler", input={"n": "not-an-int"}),
        )

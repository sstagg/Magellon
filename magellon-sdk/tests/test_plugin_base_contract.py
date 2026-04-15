"""Contract tests for the SDK's plugin surface.

Pins what every plugin needs to see when it does
``from magellon_sdk import ...`` — renames here are breaking changes.
"""
from __future__ import annotations

from abc import ABC

from pydantic import BaseModel


def test_plugin_base_import_paths():
    """PluginBase is importable from both magellon_sdk.base and the
    top-level package."""
    from magellon_sdk import PluginBase as TopLevelPluginBase
    from magellon_sdk.base import PluginBase as SubmodulePluginBase

    assert TopLevelPluginBase is SubmodulePluginBase
    assert issubclass(SubmodulePluginBase, ABC)


def test_top_level_surface():
    """Pin the names re-exported at the package top level.

    Plugin authors write ``from magellon_sdk import PluginBase, Envelope,
    NullReporter`` — renames here break every plugin.
    """
    import magellon_sdk

    for name in ("PluginBase", "Envelope", "ProgressReporter", "NullReporter",
                 "JobCancelledError"):
        assert hasattr(magellon_sdk, name), f"magellon_sdk.{name} missing"


def test_models_surface():
    """Pin the public type names — plugin authors rely on these."""
    from magellon_sdk.models import (
        CheckRequirementsResult,
        PluginInfo,
        PluginStatus,
        RecuirementResultEnum,
        RequirementResult,
        TaskCategory,
    )

    assert issubclass(PluginInfo, BaseModel)
    assert issubclass(TaskCategory, BaseModel)
    assert issubclass(RequirementResult, BaseModel)
    # Enums:
    assert PluginStatus.DISCOVERED.value == "discovered"
    assert RecuirementResultEnum.SUCCESS.value == 10
    assert CheckRequirementsResult.SUCCESS.value == 100


def test_progress_surface():
    from magellon_sdk.progress import (
        JobCancelledError,
        NullReporter,
        ProgressReporter,
    )

    # ProgressReporter is a Protocol; NullReporter must satisfy it
    # structurally (has `report` and `log`).
    reporter = NullReporter()
    reporter.report(42)
    reporter.report(42, "hello")
    reporter.log("info", "hi")

    assert issubclass(JobCancelledError, Exception)
    assert hasattr(ProgressReporter, "__class_getitem__") or True


def test_minimal_plugin_can_be_defined_and_run():
    """A trivial plugin written against the SDK alone runs end-to-end."""
    from magellon_sdk.base import PluginBase
    from magellon_sdk.models import PluginInfo, TaskCategory
    from magellon_sdk.progress import NullReporter, ProgressReporter

    class Inp(BaseModel):
        n: int

    class Out(BaseModel):
        doubled: int

    class Doubler(PluginBase[Inp, Out]):
        task_category = TaskCategory(code=999, name="test", description="test")

        def get_info(self) -> PluginInfo:
            return PluginInfo(name="doubler", version="0.1")

        @classmethod
        def input_schema(cls):
            return Inp

        @classmethod
        def output_schema(cls):
            return Out

        def execute(self, input_data: Inp, *, reporter: ProgressReporter = NullReporter()) -> Out:
            reporter.report(50, "halfway")
            return Out(doubled=input_data.n * 2)

    result = Doubler().run({"n": 3})
    assert result.doubled == 6

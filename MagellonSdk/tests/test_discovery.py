"""Discovery tests for the worker CLI.

Pin the two lookup paths: entry-point group ``magellon.plugins`` (the
packaged-distribution path) and ``MODULE:CLASSNAME`` (the unpackaged
dev path the CTF vertical slice uses today).
"""
from __future__ import annotations

from typing import Type

import pytest
from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.models import PluginInfo, TaskCategory
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.worker.discovery import PluginNotFound, load_plugin


# Module-level so MODULE:CLASSNAME resolution can find the class.


class _Inp(BaseModel):
    n: int


class _Out(BaseModel):
    doubled: int


class _FakePlugin(PluginBase[_Inp, _Out]):
    task_category = TaskCategory(code=999, name="test", description="test")

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="doubler", version="0.1")

    @classmethod
    def input_schema(cls) -> Type[_Inp]:
        return _Inp

    @classmethod
    def output_schema(cls) -> Type[_Out]:
        return _Out

    def execute(
        self,
        input_data: _Inp,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> _Out:
        return _Out(doubled=input_data.n * 2)


class _NotAPlugin:
    """Something that doesn't subclass PluginBase."""


def test_load_plugin_by_module_classname():
    plugin = load_plugin(f"{__name__}:_FakePlugin")
    assert isinstance(plugin, _FakePlugin)


def test_load_plugin_missing_module_raises():
    with pytest.raises(PluginNotFound) as exc:
        load_plugin("magellon_sdk.does.not.exist:Nope")
    assert "Could not import" in str(exc.value)


def test_load_plugin_missing_class_raises():
    with pytest.raises(PluginNotFound) as exc:
        load_plugin(f"{__name__}:DoesNotExist")
    assert "no attribute" in str(exc.value)


def test_load_plugin_rejects_non_plugin_class():
    with pytest.raises(TypeError):
        load_plugin(f"{__name__}:_NotAPlugin")


def test_load_plugin_without_colon_errors_with_help():
    """Without a colon and without an entry-point match, the error must
    tell the user how to proceed."""
    with pytest.raises(PluginNotFound) as exc:
        load_plugin("plain-name-with-no-colon")
    msg = str(exc.value)
    assert "No plugin registered" in msg
    assert "MODULE:CLASSNAME" in msg

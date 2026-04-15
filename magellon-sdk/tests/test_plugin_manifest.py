"""Tests for the plugin-manifest model and PluginBase.manifest() default.

The manifest is what the host's plugin manager consumes, so it has to:
  1. round-trip through JSON cleanly (remote plugins publish over HTTP),
  2. default sensibly for plugins that don't override anything,
  3. let plugins declare capabilities + isolation by setting class fields,
  4. allow dynamic manifest computation by overriding manifest().
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginInfo,
    PluginManifest,
    ResourceHints,
    Transport,
)


class _In(BaseModel):
    x: int


class _Out(BaseModel):
    y: int


class _MinimalPlugin(PluginBase[_In, _Out]):
    """Plugin that overrides nothing capability-wise — should get the
    safe in-process defaults."""

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="minimal", version="0.1.0")

    @classmethod
    def input_schema(cls) -> Type[_In]:
        return _In

    @classmethod
    def output_schema(cls) -> Type[_Out]:
        return _Out

    def execute(self, input_data, *, reporter=None):
        return _Out(y=input_data.x * 2)


class _MotionCorLikePlugin(PluginBase[_In, _Out]):
    """The MotionCor case from the user spec: GPU-required, memory-heavy,
    must NEVER run in-process. Declares HTTP+RMQ as transports."""

    capabilities = [
        Capability.GPU_REQUIRED,
        Capability.MEMORY_INTENSIVE,
        Capability.LONG_RUNNING,
        Capability.PROGRESS_REPORTING,
    ]
    supported_transports = [Transport.HTTP, Transport.RMQ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=32_000,
        gpu_count=1,
        gpu_memory_mb=24_000,
        typical_duration_seconds=120.0,
    )

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="motioncor-like", version="2.1.0")

    @classmethod
    def input_schema(cls) -> Type[_In]:
        return _In

    @classmethod
    def output_schema(cls) -> Type[_Out]:
        return _Out

    def execute(self, input_data, *, reporter=None):
        return _Out(y=input_data.x)


def test_default_manifest_is_safe_in_process_shape():
    """A plugin that declares nothing should be in-process, no
    capabilities, single IN_PROCESS transport. That's the conservative
    default — opt into heavier shapes deliberately."""
    m = _MinimalPlugin().manifest()

    assert m.info.name == "minimal"
    assert m.capabilities == []
    assert m.supported_transports == [Transport.IN_PROCESS]
    assert m.default_transport == Transport.IN_PROCESS
    assert m.isolation == IsolationLevel.IN_PROCESS
    assert m.resources == ResourceHints()
    assert m.can_run_in_process()


def test_motioncor_like_manifest_blocks_in_process():
    """The whole point of IsolationLevel.CONTAINER: the host must never
    accidentally import a 32 GB GPU plugin into its own process."""
    m = _MotionCorLikePlugin().manifest()

    assert m.has_capability(Capability.GPU_REQUIRED)
    assert m.has_capability(Capability.MEMORY_INTENSIVE)
    assert m.supports(Transport.HTTP)
    assert m.supports(Transport.RMQ)
    assert not m.supports(Transport.IN_PROCESS)
    assert m.default_transport == Transport.RMQ
    assert m.isolation == IsolationLevel.CONTAINER
    assert not m.can_run_in_process()

    assert m.resources.gpu_count == 1
    assert m.resources.memory_mb == 32_000
    assert m.resources.typical_duration_seconds == 120.0


def test_manifest_round_trips_through_json():
    """Remote plugins serve their manifest over HTTP; the host parses it
    with the same model. Both directions must be lossless."""
    original = _MotionCorLikePlugin().manifest()

    payload = original.model_dump_json()
    restored = PluginManifest.model_validate_json(payload)

    assert restored == original
    assert restored.has_capability(Capability.GPU_REQUIRED)
    assert restored.supported_transports == [Transport.HTTP, Transport.RMQ]
    assert restored.isolation == IsolationLevel.CONTAINER


def test_manifest_can_be_overridden_for_dynamic_capabilities():
    """A plugin that detects GPU at runtime returns a different manifest
    depending on the host. Override manifest() instead of class fields."""

    class _DynamicPlugin(_MinimalPlugin):
        def __init__(self, has_gpu: bool) -> None:
            super().__init__()
            self._has_gpu = has_gpu

        def manifest(self) -> PluginManifest:
            base = super().manifest()
            if self._has_gpu:
                base.capabilities = [Capability.GPU_OPTIONAL]
            return base

    with_gpu = _DynamicPlugin(has_gpu=True).manifest()
    without_gpu = _DynamicPlugin(has_gpu=False).manifest()

    assert with_gpu.has_capability(Capability.GPU_OPTIONAL)
    assert not without_gpu.has_capability(Capability.GPU_OPTIONAL)


def test_replaces_field_supports_drop_in_substitution():
    """The 'replaces' list is how a v2 plugin advertises that it can
    serve callers expecting v1's plugin_id — same input/output schema,
    new implementation."""

    class _V2Plugin(_MinimalPlugin):
        replaces = ["minimal-v1", "minimal-legacy"]

        def get_info(self) -> PluginInfo:
            return PluginInfo(name="minimal", version="2.0.0")

    m = _V2Plugin().manifest()
    assert m.replaces == ["minimal-v1", "minimal-legacy"]
    assert m.info.version == "2.0.0"

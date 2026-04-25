"""Unit tests for the topaz dispatch helpers.

Mocks the bus so we don't need RabbitMQ. Asserts each helper builds
the right route + envelope + payload.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from magellon_sdk.bus import get_bus
from magellon_sdk.models.tasks import (
    MICROGRAPH_DENOISING,
    MicrographDenoiseTaskData,
    TOPAZ_PARTICLE_PICKING,
    TopazPickTaskData,
)


@pytest.fixture
def fake_bus():
    bus = MagicMock()
    bus.tasks.send.return_value = MagicMock(ok=True, error=None)
    get_bus.override(bus)
    from core.dispatcher_registry import get_task_dispatcher_registry

    get_task_dispatcher_registry.cache_clear()
    yield bus
    get_bus.override(None)
    get_task_dispatcher_registry.cache_clear()


def _last_send(bus: MagicMock):
    assert bus.tasks.send.called, "bus.tasks.send was not called"
    route, envelope = bus.tasks.send.call_args.args
    return route, envelope


def test_pick_dispatch_routes_to_topaz_subject(fake_bus):
    from core.helper import dispatch_topaz_pick_task

    ok = dispatch_topaz_pick_task(
        image_path="/magellon/session/expo.mrc",
        model="resnet16", radius=14, threshold=-3.0, scale=8,
    )
    assert ok is True

    route, envelope = _last_send(fake_bus)
    assert route.subject == "magellon.tasks.topazparticlepicking"

    task = envelope.data
    assert task.type.code == TOPAZ_PARTICLE_PICKING.code

    parsed = TopazPickTaskData.model_validate(task.data)
    assert parsed.input_file == "/magellon/session/expo.mrc"
    assert parsed.engine_opts["model"] == "resnet16"
    assert parsed.engine_opts["radius"] == 14
    assert parsed.engine_opts["threshold"] == -3.0
    assert parsed.engine_opts["scale"] == 8


def test_denoise_dispatch_routes_to_denoise_subject(fake_bus):
    from core.helper import dispatch_micrograph_denoise_task

    ok = dispatch_micrograph_denoise_task(
        image_path="/magellon/session/expo.mrc",
        output_file="/magellon/session/expo_denoised.mrc",
        model="unet", patch_size=512, padding=64,
        session_name="24mar28a",
    )
    assert ok is True

    route, envelope = _last_send(fake_bus)
    assert route.subject == "magellon.tasks.micrographdenoising"

    task = envelope.data
    assert task.type.code == MICROGRAPH_DENOISING.code
    assert task.session_name == "24mar28a"

    parsed = MicrographDenoiseTaskData.model_validate(task.data)
    assert parsed.input_file == "/magellon/session/expo.mrc"
    assert parsed.output_file == "/magellon/session/expo_denoised.mrc"
    assert parsed.engine_opts["patch_size"] == 512


def test_pick_dispatch_returns_false_on_bus_failure(fake_bus):
    from core.helper import dispatch_topaz_pick_task

    fake_bus.tasks.send.return_value = MagicMock(ok=False, error="oops")
    ok = dispatch_topaz_pick_task(image_path="/x.mrc")
    assert ok is False

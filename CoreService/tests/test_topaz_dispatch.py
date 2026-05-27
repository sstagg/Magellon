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
    MicrographDenoiseInput,
    TOPAZ_PARTICLE_PICKING,
    TopazPickInput,
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

    parsed = TopazPickInput.model_validate(task.data)
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

    parsed = MicrographDenoiseInput.model_validate(task.data)
    assert parsed.input_file == "/magellon/session/expo.mrc"
    assert parsed.output_file == "/magellon/session/expo_denoised.mrc"
    assert parsed.engine_opts["patch_size"] == 512


def test_pick_dispatch_returns_false_on_bus_failure(fake_bus):
    from core.helper import dispatch_topaz_pick_task

    fake_bus.tasks.send.return_value = MagicMock(ok=False, error="oops")
    ok = dispatch_topaz_pick_task(image_path="/x.mrc")
    assert ok is False


@pytest.fixture
def live_backend_resolver(monkeypatch):
    """Resolve every backend pin to a queue so dispatch routing succeeds
    without a real liveness registry — dispatch_particle_pick_task always
    sets task.target_backend, which requires a backend resolver."""
    import core.dispatcher_registry as dr
    from core.dispatcher_registry import get_task_dispatcher_registry

    monkeypatch.setattr(
        dr, "_live_backend_queue",
        lambda contract, backend_id: f"{backend_id}_tasks_queue",
    )
    get_task_dispatcher_registry.cache_clear()
    yield
    get_task_dispatcher_registry.cache_clear()


def test_particle_pick_dispatch_nests_topaz_engine_opts(fake_bus, live_backend_resolver):
    """The UI dispatch helper routes topaz backends to the topaz
    category and nests engine knobs under ``engine_opts`` so
    ``TopazPickInput.model_validate`` actually sees them. A flat
    spread left ``engine_opts`` empty and the plugin silently fell
    back to its defaults — the threshold slider did nothing."""
    from core.helper import dispatch_particle_pick_task

    ok = dispatch_particle_pick_task(
        "/magellon/session/expo.mrc",
        target_backend="topaz",
        engine_opts={"model": "resnet8", "threshold": -1.5, "radius": 20, "scale": 4},
    )
    assert ok is True

    route, envelope = _last_send(fake_bus)
    assert route.subject.startswith("magellon.tasks.topazparticlepicking")

    task = envelope.data
    assert task.type.code == TOPAZ_PARTICLE_PICKING.code

    parsed = TopazPickInput.model_validate(task.data)
    assert parsed.engine_opts["model"] == "resnet8"
    assert parsed.engine_opts["threshold"] == -1.5
    assert parsed.engine_opts["radius"] == 20
    assert parsed.engine_opts["scale"] == 4


def test_particle_pick_dispatch_keeps_template_picker_opts_flat(fake_bus, live_backend_resolver):
    """Non-topaz backends carry typed fields at the top level — the
    template-picker plugin's TemplatePickerInput expects them there."""
    from core.helper import dispatch_particle_pick_task

    ok = dispatch_particle_pick_task(
        "/magellon/session/expo.mrc",
        target_backend="template-picker",
        engine_opts={"threshold": 0.42, "max_peaks": 300},
    )
    assert ok is True

    _route, envelope = _last_send(fake_bus)
    task = envelope.data
    assert task.data["threshold"] == 0.42
    assert task.data["max_peaks"] == 300
    assert "engine_opts" not in task.data


def test_particle_pick_dispatch_engine_opts_cannot_clear_transport_fields(
    fake_bus, live_backend_resolver
):
    """Plugin schema defaults may include nullable base fields, but
    flattening them must not wipe the task metadata the result processor
    needs to save the produced IPP record."""
    from core.helper import dispatch_particle_pick_task

    image_id = uuid.uuid4()
    ok = dispatch_particle_pick_task(
        "/magellon/session/expo.mrc",
        image_id=image_id,
        target_backend="boxnet-picker",
        ipp_name="BoxNet smoke",
        engine_opts={
            "image_id": None,
            "image_name": None,
            "image_path": None,
            "input_file": None,
            "ipp_name": None,
            "threshold": 0.3,
            "invert": True,
        },
    )
    assert ok is True

    _route, envelope = _last_send(fake_bus)
    task = envelope.data
    assert task.data["image_id"] == str(image_id)
    assert task.data["image_name"] == "expo"
    assert task.data["image_path"] == "/magellon/session/expo.mrc"
    assert task.data["input_file"] == "/magellon/session/expo.mrc"
    assert task.data["ipp_name"] == "BoxNet smoke"
    assert task.data["threshold"] == 0.3
    assert task.data["invert"] is True

"""Registry wiring test — pins which TaskCategory codes resolve to
which bus route + which legacy RMQ queue.

Pre-MB3 this pinned ``isinstance(..., RabbitmqTaskDispatcher)`` +
``disp.queue_name == "ctf_tasks_queue"``. Post-MB3 the dispatcher is
a ``_BusTaskDispatcher`` carrying a ``TaskRoute`` (subject
``magellon.tasks.ctf``). The legacy queue name has moved into the
binder's ``legacy_queue_map`` — we pin that here too so a regression
in the map surfaces before it reaches production.
"""
from __future__ import annotations

import pytest

from config import app_settings
from core.dispatcher_registry import (
    _BusTaskDispatcher,
    _build_legacy_queue_map,
    get_task_dispatcher_registry,
)
from models.plugins_models import CTF_TASK, FFT_TASK, MOTIONCOR_TASK, PARTICLE_PICKING


@pytest.mark.characterization
def test_registry_has_bus_dispatcher_for_ctf():
    disp = get_task_dispatcher_registry().get(CTF_TASK)
    assert isinstance(disp, _BusTaskDispatcher)
    assert disp.route.subject == "magellon.tasks.ctf"
    assert disp.name == "bus:ctf"


@pytest.mark.characterization
def test_registry_has_bus_dispatcher_for_motioncor():
    disp = get_task_dispatcher_registry().get(MOTIONCOR_TASK)
    assert isinstance(disp, _BusTaskDispatcher)
    assert disp.route.subject == "magellon.tasks.motioncor"
    assert disp.name == "bus:motioncor"


@pytest.mark.characterization
def test_registry_has_bus_dispatcher_for_fft():
    disp = get_task_dispatcher_registry().get(FFT_TASK)
    assert isinstance(disp, _BusTaskDispatcher)
    assert disp.route.subject == "magellon.tasks.fft"
    assert disp.name == "bus:fft"


@pytest.mark.characterization
def test_registry_returns_none_for_unregistered_type():
    """Pins today's permissive behaviour — unknown task types return
    None from .get(), and .dispatch() logs + returns False rather than
    raising. Matches the legacy get_queue_name_by_task_type contract.

    Particle picking has no registered dispatcher yet (no plugin ships
    with Magellon today), which is the stand-in for any unwired type."""
    registry = get_task_dispatcher_registry()
    assert registry.get(PARTICLE_PICKING) is None


@pytest.mark.characterization
def test_legacy_queue_map_translates_subjects_to_production_queues():
    """The bus route ``magellon.tasks.ctf`` is broker-neutral; the
    RMQ binder needs to publish to the physical queue today's CTF
    plugin listens on (``ctf_tasks_queue``). That translation lives
    in the legacy_queue_map — pin it here so a rename in
    app_settings can't silently misroute dispatches.
    """
    mapping = _build_legacy_queue_map()
    rmq = app_settings.rabbitmq_settings

    # Task queues
    assert mapping["magellon.tasks.ctf"] == rmq.CTF_QUEUE_NAME
    assert mapping["magellon.tasks.ctf"] == "ctf_tasks_queue"
    assert mapping["magellon.tasks.motioncor"] == rmq.MOTIONCOR_QUEUE_NAME
    assert mapping["magellon.tasks.motioncor"] == "motioncor_tasks_queue"
    assert mapping["magellon.tasks.fft"] == rmq.FFT_QUEUE_NAME
    assert mapping["magellon.tasks.fft"] == "fft_tasks_queue"

    # Result queues — result consumer (MB4) will subscribe on these subjects
    assert mapping["magellon.tasks.ctf.result"] == rmq.CTF_OUT_QUEUE_NAME
    assert mapping["magellon.tasks.motioncor.result"] == rmq.MOTIONCOR_OUT_QUEUE_NAME
    assert mapping["magellon.tasks.fft.result"] == rmq.FFT_OUT_QUEUE_NAME

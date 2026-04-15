"""Registry wiring test — pins which TaskCategory codes resolve to
which RMQ queues via the new :mod:`core.dispatcher_registry`.

Parallels ``test_queue_names.py`` but exercises the Protocol-based
path that now backs ``push_task_to_task_queue``.
"""
from __future__ import annotations

import pytest

from config import app_settings
from core.dispatcher_registry import get_task_dispatcher_registry
from magellon_sdk.dispatcher import RabbitmqTaskDispatcher
from models.plugins_models import CTF_TASK, MOTIONCOR_TASK, FFT_TASK, PARTICLE_PICKING


@pytest.mark.characterization
def test_registry_has_rmq_dispatcher_for_ctf():
    disp = get_task_dispatcher_registry().get(CTF_TASK)
    assert isinstance(disp, RabbitmqTaskDispatcher)
    assert disp.queue_name == app_settings.rabbitmq_settings.CTF_QUEUE_NAME
    assert disp.queue_name == "ctf_tasks_queue"


@pytest.mark.characterization
def test_registry_has_rmq_dispatcher_for_motioncor():
    disp = get_task_dispatcher_registry().get(MOTIONCOR_TASK)
    assert isinstance(disp, RabbitmqTaskDispatcher)
    assert disp.queue_name == app_settings.rabbitmq_settings.MOTIONCOR_QUEUE_NAME
    assert disp.queue_name == "motioncor_tasks_queue"


@pytest.mark.characterization
def test_registry_has_rmq_dispatcher_for_fft():
    disp = get_task_dispatcher_registry().get(FFT_TASK)
    assert isinstance(disp, RabbitmqTaskDispatcher)
    assert disp.queue_name == app_settings.rabbitmq_settings.FFT_QUEUE_NAME
    assert disp.queue_name == "fft_tasks_queue"


@pytest.mark.characterization
def test_registry_returns_none_for_unregistered_type():
    """Pins today's permissive behaviour — unknown task types return
    None from .get(), and .dispatch() logs + returns False rather than
    raising. Matches the legacy get_queue_name_by_task_type contract.

    Particle picking has no registered dispatcher yet (no plugin ships
    with Magellon today), which is the stand-in for any unwired type."""
    registry = get_task_dispatcher_registry()
    assert registry.get(PARTICLE_PICKING) is None

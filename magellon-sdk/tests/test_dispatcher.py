"""Unit tests for magellon_sdk.dispatcher.

No broker needed — these exercise the Protocol + registry contract
and the two implementations using stub handlers / monkeypatched
publish helpers.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from magellon_sdk import messaging
from magellon_sdk.dispatcher import (
    InProcessTaskDispatcher,
    RabbitmqTaskDispatcher,
    TaskDispatcher,
    TaskDispatcherRegistry,
)
from magellon_sdk.models import CTF_TASK, MOTIONCOR, TaskMessage


def _make_task(task_type=CTF_TASK) -> TaskMessage:
    return TaskMessage(data={"inputFile": "x.mrc"}, type=task_type)


# --- Protocol satisfaction ---


def test_rabbitmq_dispatcher_satisfies_protocol():
    d = RabbitmqTaskDispatcher(queue_name="q", rabbitmq_settings=object())
    assert isinstance(d, TaskDispatcher)


def test_in_process_dispatcher_satisfies_protocol():
    d = InProcessTaskDispatcher(handler=lambda t: None)
    assert isinstance(d, TaskDispatcher)


# --- InProcessTaskDispatcher ---


def test_in_process_dispatch_sync_handler():
    calls = []
    disp = InProcessTaskDispatcher(handler=lambda task: calls.append(task))
    task = _make_task()

    ok = disp.dispatch(task)

    assert ok is True
    assert calls == [task]


def test_in_process_dispatch_async_handler():
    calls = []

    async def _handler(task: TaskMessage):
        await asyncio.sleep(0)
        calls.append(task)

    disp = InProcessTaskDispatcher(handler=_handler)
    task = _make_task()

    assert disp.dispatch(task) is True
    assert calls == [task]


def test_in_process_dispatch_returns_false_on_handler_raise():
    def _boom(_):
        raise RuntimeError("nope")

    disp = InProcessTaskDispatcher(handler=_boom)
    assert disp.dispatch(_make_task()) is False


# --- RabbitmqTaskDispatcher ---


def test_rabbitmq_dispatcher_calls_publish_helper(monkeypatch):
    captured = {}

    def _fake_publish(message, queue_name, *, rabbitmq_settings):
        captured["queue"] = queue_name
        captured["settings"] = rabbitmq_settings
        captured["task_data"] = message.data
        return True

    monkeypatch.setattr(messaging, "publish_message_to_queue", _fake_publish)

    settings = MagicMock()
    disp = RabbitmqTaskDispatcher(queue_name="ctf_in", rabbitmq_settings=settings)
    task = _make_task()

    ok = disp.dispatch(task)

    assert ok is True
    assert captured["queue"] == "ctf_in"
    assert captured["settings"] is settings
    assert captured["task_data"] == {"inputFile": "x.mrc"}


def test_rabbitmq_dispatcher_propagates_helper_false(monkeypatch):
    monkeypatch.setattr(messaging, "publish_message_to_queue", lambda *a, **k: False)
    disp = RabbitmqTaskDispatcher(queue_name="q", rabbitmq_settings=object())
    assert disp.dispatch(_make_task()) is False


# --- TaskDispatcherRegistry ---


def test_registry_routes_by_task_type_code():
    ctf_calls, mc_calls = [], []
    ctf_disp = InProcessTaskDispatcher(handler=lambda t: ctf_calls.append(t), name="ctf")
    mc_disp = InProcessTaskDispatcher(handler=lambda t: mc_calls.append(t), name="mc")

    registry = TaskDispatcherRegistry()
    registry.register(CTF_TASK, ctf_disp)
    registry.register(MOTIONCOR, mc_disp)

    assert registry.dispatch(_make_task(CTF_TASK)) is True
    assert registry.dispatch(_make_task(MOTIONCOR)) is True

    assert len(ctf_calls) == 1 and len(mc_calls) == 1
    assert ctf_calls[0].type.code == CTF_TASK.code
    assert mc_calls[0].type.code == MOTIONCOR.code


def test_registry_returns_false_for_unregistered_task_type():
    registry = TaskDispatcherRegistry()
    # No registrations — any dispatch fails cleanly.
    assert registry.dispatch(_make_task(CTF_TASK)) is False


def test_registry_returns_false_when_task_has_no_type():
    registry = TaskDispatcherRegistry()
    registry.register(CTF_TASK, InProcessTaskDispatcher(handler=lambda t: None))

    task = TaskMessage(data={}, type=None)
    assert registry.dispatch(task) is False


def test_registry_get_returns_registered_dispatcher():
    disp = InProcessTaskDispatcher(handler=lambda t: None)
    registry = TaskDispatcherRegistry()
    registry.register(CTF_TASK, disp)

    assert registry.get(CTF_TASK) is disp
    assert registry.get(MOTIONCOR) is None

"""Tests for the CTF_VIA_TEMPORAL feature flag (Phase 2 PR 2.4).

Two kinds of assertions:

1. Flag resolution — env var beats settings, truthy variants normalised,
   default is off. The flag is how staging rolls back, so the semantics
   have to be boring and predictable.

2. Dispatch routing — with the flag off, ``dispatch_ctf_task`` still
   goes through the legacy ``push_task_to_task_queue`` (RabbitMQ). With
   it on, it goes through Temporal. We monkey-patch the Temporal
   ``Client.connect`` so the test doesn't need a live server, and
   capture the ``start_workflow`` arguments to prove the host and
   worker will meet on the same queue/activity.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# Flag resolution
# ---------------------------------------------------------------------------


def test_flag_default_is_off(monkeypatch):
    """Freshly-installed CoreService must not silently route through
    Temporal. Off is the safe default."""
    monkeypatch.delenv("CTF_VIA_TEMPORAL", raising=False)
    from services.temporal_dispatch import ctf_via_temporal_enabled
    # Settings-side default is False (see TemporalSettings).
    assert ctf_via_temporal_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "  True  "])
def test_flag_env_truthy_values(monkeypatch, value):
    monkeypatch.setenv("CTF_VIA_TEMPORAL", value)
    from services.temporal_dispatch import ctf_via_temporal_enabled
    assert ctf_via_temporal_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "garbage"])
def test_flag_env_falsy_values(monkeypatch, value):
    monkeypatch.setenv("CTF_VIA_TEMPORAL", value)
    from services.temporal_dispatch import ctf_via_temporal_enabled
    assert ctf_via_temporal_enabled() is False


def test_flag_env_overrides_settings(monkeypatch):
    """Operators flip the flag with an env var on a running container —
    the setting in the YAML file must not beat an explicit env var."""
    monkeypatch.setenv("CTF_VIA_TEMPORAL", "1")
    from config import app_settings
    from services.temporal_dispatch import ctf_via_temporal_enabled

    # Even if YAML says off, env says on.
    monkeypatch.setattr(
        app_settings.temporal_settings, "CTF_VIA_TEMPORAL", False, raising=False
    )
    assert ctf_via_temporal_enabled() is True


# ---------------------------------------------------------------------------
# Dispatch routing
# ---------------------------------------------------------------------------


class _FakeHandle:
    def __init__(self) -> None:
        self.result_run_id = "fake-run-id"


class _FakeClient:
    """Captures start_workflow calls so the test can assert on them."""

    calls: List[Dict[str, Any]] = []

    @classmethod
    async def connect(cls, target: str, namespace: str = "default") -> "_FakeClient":
        inst = cls()
        inst.target = target
        inst.namespace = namespace
        return inst

    async def start_workflow(self, workflow, payload, *, id: str, task_queue: str):
        _FakeClient.calls.append(
            {
                "workflow": workflow,
                "payload": payload,
                "id": id,
                "task_queue": task_queue,
                "target": self.target,
                "namespace": self.namespace,
            }
        )
        return _FakeHandle()


@pytest.fixture(autouse=True)
def _reset_fake_client_calls():
    _FakeClient.calls.clear()
    yield
    _FakeClient.calls.clear()


def test_flag_off_uses_rabbitmq_path(monkeypatch):
    """With the flag off, nothing about the RabbitMQ dispatch changes —
    ``push_task_to_task_queue`` is still the terminal call."""
    monkeypatch.setenv("CTF_VIA_TEMPORAL", "0")

    captured = {}
    from core import helper

    def fake_push(task) -> bool:
        captured["task"] = task
        return True

    monkeypatch.setattr(helper, "push_task_to_task_queue", fake_push)

    from models.pydantic_models import ImportTaskDto

    task_dto = ImportTaskDto(
        task_id=uuid.uuid4(),
        image_id=uuid.uuid4(),
        image_path="/gpfs/test.mrc",
        image_name="test",
        frame_name="test",
        pixel_size=1e-10,
        acceleration_voltage=300,
        spherical_aberration=2.7,
        amplitude_contrast=0.07,
        size_of_amplitude_spectrum=512,
        minimum_resolution=30,
        maximum_resolution=5,
        minimum_defocus=5000,
        maximum_defocus=50000,
        defocus_search_step=500,
        binning_x=1,
    )

    ok = helper.dispatch_ctf_task(
        task_id=task_dto.task_id,
        full_image_path="/gpfs/test.mrc",
        task_dto=task_dto,
    )
    assert ok is True
    assert "task" in captured, "RabbitMQ path must still be hit when flag is off"


def test_flag_on_starts_ctf_workflow(monkeypatch):
    """With the flag on, dispatch goes through Temporal. Assert the
    host will meet the CTF plugin worker on the canonical queue and
    that the payload carries the plugin id + input data."""
    monkeypatch.setenv("CTF_VIA_TEMPORAL", "1")

    # Block the legacy path so we'd notice if routing regressed.
    from core import helper

    def fail_push(task) -> bool:
        raise AssertionError("RabbitMQ path must not run when flag is on")

    monkeypatch.setattr(helper, "push_task_to_task_queue", fail_push)

    # Swap the Temporal client for the capture fake.
    from temporalio import client as temporal_client_module

    monkeypatch.setattr(temporal_client_module, "Client", _FakeClient)

    from models.pydantic_models import ImportTaskDto
    from workflows.ctf_workflow import CTF_TASK_QUEUE

    task_id = uuid.uuid4()
    task_dto = ImportTaskDto(
        task_id=task_id,
        image_id=uuid.uuid4(),
        image_path="/gpfs/test.mrc",
        image_name="test",
        frame_name="test",
        pixel_size=1e-10,
        acceleration_voltage=300,
        spherical_aberration=2.7,
        amplitude_contrast=0.07,
        size_of_amplitude_spectrum=512,
        minimum_resolution=30,
        maximum_resolution=5,
        minimum_defocus=5000,
        maximum_defocus=50000,
        defocus_search_step=500,
        binning_x=1,
    )

    ok = helper.dispatch_ctf_task(
        task_id=task_id,
        full_image_path="/gpfs/test.mrc",
        task_dto=task_dto,
    )
    assert ok is True

    assert len(_FakeClient.calls) == 1
    call = _FakeClient.calls[0]
    assert call["task_queue"] == CTF_TASK_QUEUE
    assert call["id"].startswith("ctf-")
    assert call["payload"].plugin_id == "ctf/ctffind"
    # Payload.input must carry the CtfTaskData that helper built.
    assert call["payload"].input["inputFile"] == "/gpfs/test.mrc"

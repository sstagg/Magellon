"""Verify ``do_execute`` emits the right step events in the right order.

Mirror of the CTF plugin's wiring tests — the contract is shared
across plugins, so the tests are too. If you change one, change
this one and the MotionCor one.
"""
from __future__ import annotations

from uuid import uuid4

import pytest


class RecordingPublisher:
    def __init__(self):
        self.calls = []

    async def started(self, **kw):
        self.calls.append(("started", kw))

    async def completed(self, **kw):
        self.calls.append(("completed", kw))

    async def failed(self, **kw):
        self.calls.append(("failed", kw))


@pytest.fixture()
def recording_publisher(monkeypatch):
    pub = RecordingPublisher()
    from service import step_events
    from service import service as svc_mod

    async def _get_publisher():
        return pub

    monkeypatch.setattr(step_events, "get_publisher", _get_publisher)
    monkeypatch.setattr(svc_mod, "get_publisher", _get_publisher)
    return pub


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_completed_on_success(
    recording_publisher, monkeypatch, tmp_path
):
    from service import service as svc_mod

    # Stub compute_file_fft — we're testing wiring, not the algorithm.
    # The real FFT would need a valid mrc/tiff file on disk.
    captured = {}

    def _fake_fft(image_path, abs_out_file_name, height=1024):
        captured["image_path"] = image_path
        captured["out"] = abs_out_file_name
        return abs_out_file_name

    monkeypatch.setattr(svc_mod, "compute_file_fft", _fake_fft)

    params = _task_dto(
        image_path=str(tmp_path / "img.mrc"),
        target_path=str(tmp_path / "img_FFT.png"),
    )
    result = await svc_mod.do_execute(params)

    assert result["message"] == "FFT successfully executed"
    assert captured["image_path"] == str(tmp_path / "img.mrc")
    assert captured["out"] == str(tmp_path / "img_FFT.png")

    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "completed"]
    for _, kw in recording_publisher.calls:
        assert kw["job_id"] == params.job_id
        assert kw["task_id"] == params.id
        assert kw["step"] == "fft"
    # completed event must carry the output_files breadcrumb.
    assert recording_publisher.calls[1][1]["output_files"] == [
        str(tmp_path / "img_FFT.png")
    ]


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_failed_on_error(
    recording_publisher, monkeypatch, tmp_path
):
    from service import service as svc_mod

    def _boom(image_path, abs_out_file_name, height=1024):
        raise RuntimeError("fft crashed")

    monkeypatch.setattr(svc_mod, "compute_file_fft", _boom)

    params = _task_dto(
        image_path=str(tmp_path / "img.mrc"),
        target_path=str(tmp_path / "out.png"),
    )
    result = await svc_mod.do_execute(params)

    assert result == {"error": "fft crashed"}
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "failed"]
    assert recording_publisher.calls[1][1]["error"] == "fft crashed"


@pytest.mark.asyncio
async def test_missing_image_path_surfaces_as_failed(
    recording_publisher, monkeypatch
):
    """A task with neither image_path nor target_path must fail cleanly
    — we emit ``failed`` with a descriptive error rather than crashing
    the consumer."""
    from service import service as svc_mod

    params = _task_dto(image_path=None, target_path=None)
    result = await svc_mod.do_execute(params)

    assert "error" in result
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "failed"]


@pytest.mark.asyncio
async def test_no_emits_when_publisher_disabled(monkeypatch, tmp_path):
    from service import service as svc_mod

    async def _no_pub():
        return None

    monkeypatch.setattr(svc_mod, "get_publisher", _no_pub)

    def _fake_fft(image_path, abs_out_file_name, height=1024):
        return abs_out_file_name

    monkeypatch.setattr(svc_mod, "compute_file_fft", _fake_fft)

    params = _task_dto(
        image_path=str(tmp_path / "img.mrc"),
        target_path=str(tmp_path / "out.png"),
    )
    result = await svc_mod.do_execute(params)
    assert result["message"] == "FFT successfully executed"


def _task_dto(*, image_path=None, target_path=None):
    from magellon_sdk.models.tasks import TaskDto

    data = {}
    if image_path is not None:
        data["image_path"] = image_path
    if target_path is not None:
        data["target_path"] = target_path
    return TaskDto(id=uuid4(), job_id=uuid4(), data=data)

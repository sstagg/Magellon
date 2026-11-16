"""Batch particle picking settles its job: done when any image worked, failed when none did."""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

import controllers.particle_picking_controller as pp
from services.particle_picking.models import BatchImageEntry, BatchPickRequest


class Jobs:
    def __init__(self):
        self.calls = []

    def mark_running(self, job_id, progress=0):
        return {}

    def is_cancelled(self, job_id):
        return False

    def update_progress(self, job_id, **kw):
        return {}

    def complete_job(self, job_id, **kw):
        self.calls.append(("complete", kw))
        return {}

    def fail_job(self, job_id, error):
        self.calls.append(("fail", error))
        return {}

    def create_job(self, **kw):
        self.calls.append(("create", kw))
        return {"job_id": "j1"}


@pytest.fixture
def batch(monkeypatch, tmp_path):
    jobs = Jobs()
    monkeypatch.setattr(pp, "job_manager", jobs)
    image = SimpleNamespace(session_id=uuid.uuid4(), path=None)
    db = SimpleNamespace(query=lambda *a: SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: image)),
                         close=lambda: None)
    monkeypatch.setattr(pp, "get_db", lambda: iter([db]))
    monkeypatch.setattr(pp, "check_session_access", lambda *a, **k: True)
    mrc = tmp_path / "a.mrc"
    mrc.write_bytes(b"x")
    monkeypatch.setattr(pp, "_resolve_mrc_path", lambda *a, **k: str(mrc))
    monkeypatch.setattr(pp, "_save_particle_picking", lambda *a: None)
    import core.socketio_server as sio

    async def nothing(*a, **k):
        return None
    monkeypatch.setattr(sio, "emit_job_update", nothing)
    monkeypatch.setattr(sio, "emit_log", nothing)
    request = BatchPickRequest(session_name="s", ipp_name="Topaz batch", backend="topaz-particle-picking",
                               picker_params={"model": "resnet16"},
                               images=[BatchImageEntry(oid=str(uuid.uuid4()), name=f"img{i}") for i in range(2)])
    return jobs, request


def run(request):
    asyncio.run(pp._run_batch_job("j1", request, "u1", None))


def test_a_batch_where_every_image_failed_is_failed(batch, monkeypatch):
    jobs, request = batch

    def refuse(*a, **k):
        raise RuntimeError("Read-only file system")
    monkeypatch.setattr(pp, "dispatch_capability", refuse)
    run(request)
    assert [c[0] for c in jobs.calls] == ["fail"]
    assert "All 2 images failed" in jobs.calls[0][1] and "Read-only" in jobs.calls[0][1]


def test_a_batch_with_any_success_completes(batch, monkeypatch):
    jobs, request = batch
    monkeypatch.setattr(pp, "dispatch_capability", lambda *a, **k: {"particles_json_path": None, "image_shape": [4, 4]})
    run(request)
    assert [c[0] for c in jobs.calls] == ["complete"]
    assert jobs.calls[0][1]["result"]["succeeded"] == 2


def test_the_batch_job_has_no_task_rows_to_wait_for(batch, monkeypatch):
    jobs, request = batch

    async def no_run(*a, **k):
        return None
    monkeypatch.setattr(pp, "_run_batch_job", no_run)

    async def start():
        await pp.template_pick_batch(request, None, uuid.uuid4())
        await asyncio.sleep(0)
    asyncio.run(start())
    create = next(c[1] for c in jobs.calls if c[0] == "create")
    assert "image_ids" not in create and "task_ids" not in create
    assert create["settings"]["image_ids"] == [e.oid for e in request.images]

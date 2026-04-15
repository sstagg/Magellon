"""HTTP contract test for POST /fft/dispatch.

Exercises the router with a stubbed dispatch_fft_task so we verify
the endpoint's request/response shape and target_path generation
without touching RMQ.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """Per-test client — module scope would share monkeypatches
    across tests which is brittle when each test patches
    dispatch_fft_task differently."""
    from dependencies.auth import get_current_user_id

    from controllers.image_processing_controller import image_processing_router

    # Bypass Casbin — each require_permission call builds a fresh
    # closure, so we stub CasbinService.enforce (and user auth) rather
    # than the dependency factory's return value.
    from services.casbin_service import CasbinService

    monkeypatch.setattr(CasbinService, "enforce", staticmethod(lambda *a, **kw: True))

    app = FastAPI()
    app.include_router(image_processing_router)
    app.dependency_overrides[get_current_user_id] = lambda: uuid4()
    return TestClient(app)


def test_dispatch_with_explicit_target_path(client, monkeypatch):
    captured = {}

    def _fake_dispatch(*, image_path, target_path, job_id=None, task_id=None, image_id=None):
        captured["image_path"] = image_path
        captured["target_path"] = target_path
        captured["job_id"] = job_id
        captured["task_id"] = task_id
        return True

    import core.helper as helper_mod
    monkeypatch.setattr(helper_mod, "dispatch_fft_task", _fake_dispatch)

    resp = client.post(
        "/fft/dispatch",
        json={
            "image_path": "/data/sample.mrc",
            "target_path": "/out/sample_FFT.png",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "dispatched"
    assert body["queue_name"] == "fft_tasks_queue"
    assert body["image_path"] == "/data/sample.mrc"
    assert body["target_path"] == "/out/sample_FFT.png"

    # IDs must round-trip as valid UUIDs the UI can use for a job-room subscription.
    UUID(body["job_id"])
    UUID(body["task_id"])
    assert captured["image_path"] == "/data/sample.mrc"
    assert captured["target_path"] == "/out/sample_FFT.png"


def test_dispatch_generates_sibling_target_when_unset(client, monkeypatch):
    captured = {}

    def _fake_dispatch(*, image_path, target_path, **kw):
        captured["target_path"] = target_path
        return True

    import core.helper as helper_mod
    monkeypatch.setattr(helper_mod, "dispatch_fft_task", _fake_dispatch)

    resp = client.post("/fft/dispatch", json={"image_path": "/data/img.mrc"})
    assert resp.status_code == 200, resp.text

    # Default convention mirrors mrc_image_service.compute_dir_fft:
    # <stem>_FFT.png next to the input.
    assert captured["target_path"].replace("\\", "/") == "/data/img_FFT.png"
    assert resp.json()["target_path"].replace("\\", "/") == "/data/img_FFT.png"


def test_dispatch_returns_502_on_publish_failure(client, monkeypatch):
    import core.helper as helper_mod
    monkeypatch.setattr(helper_mod, "dispatch_fft_task", lambda **kw: False)

    resp = client.post("/fft/dispatch", json={"image_path": "/data/img.mrc"})
    assert resp.status_code == 502
    assert "Failed to publish" in resp.json()["detail"]


def test_dispatch_respects_provided_job_id(client, monkeypatch):
    """A caller-provided job_id lets the UI open the Socket.IO room
    before the dispatch returns, removing a race on first emits."""
    captured = {}

    def _fake_dispatch(*, image_path, target_path, job_id=None, task_id=None, image_id=None):
        captured["job_id"] = job_id
        return True

    import core.helper as helper_mod
    monkeypatch.setattr(helper_mod, "dispatch_fft_task", _fake_dispatch)

    fixed = str(uuid4())
    resp = client.post(
        "/fft/dispatch",
        json={"image_path": "/data/img.mrc", "job_id": fixed},
    )
    assert resp.status_code == 200
    assert resp.json()["job_id"] == fixed
    assert str(captured["job_id"]) == fixed

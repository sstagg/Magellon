"""Tests for the SDK capability routers (PT-2)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from magellon_sdk.capabilities import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
    make_preview_router,
    make_sync_router,
)


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class _DummyInput(BaseModel):
    image_path: str
    threshold: float = 0.4


class _DummyOutput(BaseModel):
    n_particles: int
    success: bool = True


# ---------------------------------------------------------------------------
# SYNC router
# ---------------------------------------------------------------------------


class _SyncOnlyPlugin:
    """Minimal plugin shape that satisfies make_sync_router's contract."""

    @staticmethod
    def input_schema():
        return _DummyInput

    @staticmethod
    def output_schema():
        return _DummyOutput

    def execute_sync(self, input_data: _DummyInput) -> _DummyOutput:
        if input_data.image_path == "missing.mrc":
            raise FileNotFoundError("missing.mrc not found")
        if input_data.threshold > 1.0:
            raise ValueError("threshold > 1")
        return _DummyOutput(n_particles=42)


def _client_with_sync(plugin) -> TestClient:
    app = FastAPI()
    app.include_router(make_sync_router(plugin))
    return TestClient(app)


def test_sync_router_returns_output_for_valid_input():
    client = _client_with_sync(_SyncOnlyPlugin())
    resp = client.post("/execute", json={"image_path": "img.mrc"})
    assert resp.status_code == 200
    assert resp.json() == {"n_particles": 42, "success": True}


def test_sync_router_maps_value_error_to_422():
    client = _client_with_sync(_SyncOnlyPlugin())
    resp = client.post("/execute", json={"image_path": "img.mrc", "threshold": 5.0})
    assert resp.status_code == 422
    assert "threshold > 1" in resp.json()["detail"]


def test_sync_router_maps_file_not_found_to_404():
    client = _client_with_sync(_SyncOnlyPlugin())
    resp = client.post("/execute", json={"image_path": "missing.mrc"})
    assert resp.status_code == 404


def test_sync_router_rejects_plugin_without_execute_sync():
    """A plugin advertising Capability.SYNC but not implementing
    execute_sync is a clear bug — surface at mount time, not at
    request time."""
    bad_plugin = SimpleNamespace(
        input_schema=lambda: _DummyInput,
        output_schema=lambda: _DummyOutput,
    )
    with pytest.raises(TypeError, match="execute_sync"):
        make_sync_router(bad_plugin)


# ---------------------------------------------------------------------------
# PREVIEW router
# ---------------------------------------------------------------------------


class _FakePreviewCache:
    """Stand-in for the TTLCache a real picker holds."""

    def __init__(self):
        self._store = {}

    def store(self, preview_id, payload):
        self._store[preview_id] = payload

    def get(self, preview_id):
        return self._store.get(preview_id)

    def pop(self, preview_id):
        return self._store.pop(preview_id, None)


class _PreviewPlugin:
    """Minimal plugin implementing the PREVIEW contract."""

    def __init__(self):
        self._cache = _FakePreviewCache()
        self._next_id = 0

    @staticmethod
    def input_schema():
        return _DummyInput

    def preview(self, input_data: _DummyInput) -> PickingPreviewResult:
        self._next_id += 1
        preview_id = f"prev-{self._next_id}"
        self._cache.store(preview_id, {"threshold": input_data.threshold})
        return PickingPreviewResult(
            preview_id=preview_id,
            particles=[
                {"x": 100, "y": 200, "score": 0.9},
                {"x": 300, "y": 400, "score": 0.7},
            ],
            num_particles=2,
            num_templates=1,
            target_pixel_size=1.0,
            image_binning=1,
        )

    def retune(self, preview_id, params) -> Optional[PickingRetuneResult]:
        if self._cache.get(preview_id) is None:
            return None
        # Pretend the new threshold filters: include only score >= threshold.
        kept = [
            {"x": 100, "y": 200, "score": 0.9},
        ] if params.threshold <= 0.8 else []
        return PickingRetuneResult(
            particles=kept, num_particles=len(kept),
        )

    def discard_preview(self, preview_id) -> bool:
        return self._cache.pop(preview_id) is not None


def _client_with_preview(plugin) -> TestClient:
    app = FastAPI()
    app.include_router(make_preview_router(plugin))
    return TestClient(app)


def test_preview_router_returns_preview_id_and_initial_picks():
    client = _client_with_preview(_PreviewPlugin())
    resp = client.post("/preview", json={"image_path": "img.mrc"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["preview_id"]
    assert body["num_particles"] == 2


def test_preview_router_retune_uses_cached_state():
    plugin = _PreviewPlugin()
    client = _client_with_preview(plugin)

    preview_id = client.post("/preview", json={"image_path": "img.mrc"}).json()["preview_id"]

    resp = client.post(
        f"/preview/{preview_id}/retune",
        json={"threshold": 0.5, "max_peaks": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["num_particles"] == 1


def test_preview_router_retune_404s_for_unknown_id():
    client = _client_with_preview(_PreviewPlugin())
    resp = client.post(
        "/preview/never-existed/retune",
        json={"threshold": 0.5, "max_peaks": 100},
    )
    assert resp.status_code == 404


def test_preview_router_delete_removes_cached_preview():
    plugin = _PreviewPlugin()
    client = _client_with_preview(plugin)

    preview_id = client.post("/preview", json={"image_path": "img.mrc"}).json()["preview_id"]
    assert client.delete(f"/preview/{preview_id}").status_code == 200
    # Subsequent retune should now 404.
    assert client.post(
        f"/preview/{preview_id}/retune",
        json={"threshold": 0.5, "max_peaks": 100},
    ).status_code == 404


def test_preview_router_delete_404s_for_unknown_id():
    client = _client_with_preview(_PreviewPlugin())
    assert client.delete("/preview/never-existed").status_code == 404


def test_preview_router_rejects_plugin_missing_methods():
    """A plugin advertising Capability.PREVIEW must implement all three
    methods. Surface incomplete implementations at mount time."""
    bad = SimpleNamespace(input_schema=lambda: _DummyInput)  # no preview/retune/discard
    with pytest.raises(TypeError, match="preview"):
        make_preview_router(bad)

"""Smoke tests for the /system/stats endpoint.

We're not asserting concrete CPU/RAM numbers — those are flaky by
nature. We pin: shape, status code, gating, GPU graceful-fallback.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import system_stats_controller as ctl
from dependencies.permissions import require_role


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ctl.system_stats_router, prefix="/system")
    # Open the gate for tests — production keeps Administrator.
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for dep in dependant.dependencies:
                if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                    app.dependency_overrides[dep.call] = lambda: None
    app.dependency_overrides[require_role("Administrator")] = lambda: None
    return TestClient(app)


def test_stats_returns_200_with_expected_shape(client):
    resp = client.get("/system/stats")
    assert resp.status_code == 200
    body = resp.json()
    # Top-level keys
    for key in ("cpu", "ram", "network", "gpu", "sampled_at"):
        assert key in body
    # CPU shape
    assert isinstance(body["cpu"]["percent"], (int, float))
    assert isinstance(body["cpu"]["cores"], int) and body["cpu"]["cores"] >= 0
    # RAM shape
    for key in ("total_bytes", "used_bytes", "available_bytes", "percent"):
        assert key in body["ram"]
    assert body["ram"]["total_bytes"] > 0
    # Network shape
    for key in ("rx_bytes_per_sec", "tx_bytes_per_sec", "rx_total_bytes", "tx_total_bytes"):
        assert key in body["network"]
    # GPU shape
    assert "available" in body["gpu"]
    assert isinstance(body["gpu"]["devices"], list)


def test_stats_gpu_falls_back_gracefully_when_no_nvml(client):
    """No NVML, no nvidia-smi → ``gpu.available`` is False, no error."""
    with patch.object(ctl, "_gpu_via_pynvml", return_value=None), \
         patch.object(ctl, "_gpu_via_smi", return_value=None):
        resp = client.get("/system/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["gpu"]["available"] is False
        assert body["gpu"]["devices"] == []


def test_network_rate_computes_delta_between_calls(client, monkeypatch):
    """First call seeds the cache, second call returns a non-trivial
    delta when bytes move between samples. We mock psutil.net_io_counters
    so the test is deterministic."""
    # Reset module-level state before exercising
    monkeypatch.setattr(ctl, "_net_last", None, raising=False)

    class _Counters:
        def __init__(self, recv: int, sent: int) -> None:
            self.bytes_recv = recv
            self.bytes_sent = sent

    seq = iter([_Counters(1000, 500), _Counters(3000, 1500)])

    def _next(*args, **kwargs):
        return next(seq)

    # Fake monotonic so dt = 1.0 between samples — we get 2000 rx/s, 1000 tx/s.
    times = iter([100.0, 101.0])
    monkeypatch.setattr(ctl.psutil, "net_io_counters", _next)
    monkeypatch.setattr(ctl.time, "monotonic", lambda: next(times))

    first = ctl._net_rate()
    assert first.rx_bytes_per_sec == 0.0  # first call has no prior sample
    second = ctl._net_rate()
    assert second.rx_bytes_per_sec == pytest.approx(2000.0)
    assert second.tx_bytes_per_sec == pytest.approx(1000.0)
    assert second.rx_total_bytes == 3000

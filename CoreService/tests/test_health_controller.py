from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import health_controller as ctl


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(ctl.health_router, prefix="/health")
    return TestClient(app)


def test_live_returns_ok():
    resp = _client().get("/health/live")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_returns_200_when_required_checks_pass(monkeypatch):
    monkeypatch.setattr(ctl, "_check_database", lambda: (True, {"status": "ok"}))
    monkeypatch.setattr(ctl, "_check_bus", lambda: (True, {"status": "ok", "type": "MockBus"}))
    monkeypatch.setenv("MAGELLON_RMQ_STEP_EVENTS_FORWARDER", "0")
    monkeypatch.setenv("MAGELLON_STEP_EVENTS_FORWARDER", "0")
    monkeypatch.setenv("MAGELLON_PLUGIN_LIVENESS_LISTENER", "0")
    monkeypatch.setenv("MAGELLON_OPERATIONAL_EVENT_LOGGER", "0")

    resp = _client().get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["message_bus"]["type"] == "MockBus"


def test_ready_returns_503_when_required_check_fails(monkeypatch):
    monkeypatch.setattr(ctl, "_check_database", lambda: (False, {"status": "error"}))
    monkeypatch.setattr(ctl, "_check_bus", lambda: (True, {"status": "ok"}))

    resp = _client().get("/health/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"


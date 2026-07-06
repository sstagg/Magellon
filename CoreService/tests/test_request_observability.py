from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.request_observability import (
    PROCESS_TIME_HEADER,
    REQUEST_ID_HEADER,
    register_request_observability,
)


def _client() -> TestClient:
    app = FastAPI()
    register_request_observability(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    return TestClient(app)


def test_request_observability_adds_correlation_headers():
    resp = _client().get("/ok")

    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER]
    assert float(resp.headers[PROCESS_TIME_HEADER]) >= 0


def test_request_observability_preserves_inbound_request_id():
    resp = _client().get("/ok", headers={REQUEST_ID_HEADER: "req-123"})

    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] == "req-123"

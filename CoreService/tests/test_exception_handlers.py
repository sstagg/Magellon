from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.exception_handlers import register_exception_handlers
from core.exceptions import EntityNotFoundError


def test_domain_exception_keeps_message_and_cors_headers():
    app = FastAPI()
    register_exception_handlers(app, is_production=lambda: False)

    @app.get("/missing")
    def missing():
        raise EntityNotFoundError("Thing", "abc")

    resp = TestClient(app).get("/missing", headers={"Origin": "http://localhost"})

    assert resp.status_code == 404
    assert "Thing" in resp.json()["message"]
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost"


def test_unhandled_exception_is_redacted_in_production():
    app = FastAPI()
    register_exception_handlers(app, is_production=lambda: True)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret implementation detail")

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {
        "message": "Internal server error",
        "path": "/boom",
    }


def test_unhandled_exception_is_verbose_outside_production():
    app = FastAPI()
    register_exception_handlers(app, is_production=lambda: False)

    @app.get("/boom")
    def boom():
        raise RuntimeError("debug detail")

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert resp.status_code == 500
    assert "RuntimeError: debug detail" == resp.json()["message"]


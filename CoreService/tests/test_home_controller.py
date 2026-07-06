from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import home_controller as ctl


def test_redact_config_masks_nested_sensitive_values():
    payload = {
        "database_settings": {
            "DB_HOST": "db",
            "DB_PASSWORD": "secret",
        },
        "api_docs_settings": {
            "USERNAME": "admin",
            "PASSWORD": "docs-secret",
        },
        "items": [
            {"api_key": "sk-test", "name": "public"},
            {"token": None},
        ],
    }

    redacted = ctl._redact_config(payload)

    assert redacted["database_settings"]["DB_HOST"] == "db"
    assert redacted["database_settings"]["DB_PASSWORD"] == "<redacted>"
    assert redacted["api_docs_settings"]["PASSWORD"] == "<redacted>"
    assert redacted["items"][0]["api_key"] == "<redacted>"
    assert redacted["items"][0]["name"] == "public"
    assert redacted["items"][1]["token"] is None


def test_configs_endpoint_returns_redacted_settings_for_admin():
    app = FastAPI()
    app.include_router(ctl.home_router)

    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for dep in dependant.dependencies:
                if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                    app.dependency_overrides[dep.call] = lambda: {"user_id": uuid4()}

    resp = TestClient(app).get("/configs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["database_settings"]["DB_PASSWORD"] in (None, "<redacted>")
    assert body["rabbitmq_settings"]["PASSWORD"] in (None, "<redacted>")
    assert body["api_docs_settings"]["PASSWORD"] in (None, "<redacted>")
    assert body["security_setup_settings"]["SETUP_TOKEN"] in (None, "<redacted>")


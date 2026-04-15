"""HTTP contract tests for the generic plugins router.

Pins the JSON shape of the public endpoints under `/plugins/`. These are
the contracts the React app and third-party plugin consumers rely on.

Uses a minimal FastAPI app to avoid booting CoreService's DB-bound
startup hooks — we're testing the router's contract, not main.py's wiring.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plugins.controller import plugins_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(plugins_router, prefix="/plugins")
    return TestClient(app)


@pytest.mark.characterization
def test_list_plugins_shape(client):
    resp = client.get("/plugins/")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1

    # Every entry must carry these fields — they drive the plugin picker UI.
    required = {"plugin_id", "category", "name", "version", "schema_version", "description", "developer"}
    for entry in body:
        assert required.issubset(entry.keys()), f"Missing keys in {entry}"


@pytest.mark.characterization
def test_list_plugins_contains_expected_ids(client):
    body = client.get("/plugins/").json()
    ids = {entry["plugin_id"] for entry in body}
    assert {"ctf/ctffind", "motioncor/motioncor2", "pp/template-picker"}.issubset(ids)


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_info_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/info")
    assert resp.status_code == 200
    info = resp.json()
    assert info["name"] == plugin_id.split("/", 1)[1]
    assert "version" in info
    assert "schema_version" in info


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_input_schema_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/schema/input")
    assert resp.status_code == 200
    schema = resp.json()
    # JSON Schema envelope — the React form generator depends on these keys.
    assert schema.get("type") == "object" or "properties" in schema or "$ref" in schema


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", [
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
])
def test_plugin_output_schema_endpoint(client, plugin_id):
    resp = client.get(f"/plugins/{plugin_id}/schema/output")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema.get("type") == "object" or "properties" in schema or "$ref" in schema


@pytest.mark.characterization
def test_unknown_plugin_returns_404(client):
    resp = client.get("/plugins/does-not-exist/info")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.characterization
def test_submit_job_validates_input(client):
    """Bad input → 422 with a helpful detail, not a 500."""
    resp = client.post(
        "/plugins/ctf/ctffind/jobs",
        json={"input": {"clearly": "wrong"}},
    )
    assert resp.status_code == 422
    assert "Invalid input" in resp.json()["detail"]


@pytest.mark.characterization
def test_cancel_unknown_job_returns_404(client):
    resp = client.delete("/plugins/jobs/00000000-0000-0000-0000-000000000999")
    assert resp.status_code == 404

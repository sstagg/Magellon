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

    # Every entry must carry these fields — they drive the plugin picker UI
    # and now also the manager's transport/isolation routing decisions.
    required = {
        "plugin_id", "category", "name", "version", "schema_version",
        "description", "developer",
        # New capability surface — added with the PluginManifest work
        "capabilities", "supported_transports", "default_transport", "isolation",
    }
    for entry in body:
        assert required.issubset(entry.keys()), f"Missing keys in {entry}"


@pytest.mark.characterization
def test_template_picker_advertises_real_capabilities(client):
    """Template-picker is the worked example of a plugin that opts into
    the new capability fields. Discovery must surface them so a UI/
    manager can route accordingly without fetching the full manifest."""
    body = client.get("/plugins/").json()
    tp = next(e for e in body if e["plugin_id"] == "pp/template-picker")
    assert "cpu_intensive" in tp["capabilities"]
    assert "progress_reporting" in tp["capabilities"]
    assert "in_process" in tp["supported_transports"]
    assert "http" in tp["supported_transports"]
    assert tp["isolation"] == "in_process"


@pytest.mark.characterization
def test_motioncor_advertises_gpu_and_container_isolation(client):
    """MotionCor is the canonical "don't run me in-process" plugin.
    The manifest must reflect that so the future dispatcher knows to
    route it to a GPU container, not the backend process itself —
    this is why the manifest field exists at all."""
    body = client.get("/plugins/").json()
    mc = next(e for e in body if e["plugin_id"] == "motioncor/motioncor2")
    assert "gpu_required" in mc["capabilities"]
    assert "memory_intensive" in mc["capabilities"]
    assert "long_running" in mc["capabilities"]
    assert mc["isolation"] == "container"

    # Manifest endpoint exposes the resource hints a scheduler needs.
    m = client.get("/plugins/motioncor/motioncor2/manifest").json()
    assert m["resources"]["gpu_count"] == 1
    assert m["resources"]["memory_mb"] >= 16_000


@pytest.mark.characterization
def test_ctffind_advertises_cpu_only_shape(client):
    """Sanity check that ctffind doesn't accidentally claim GPU — it's
    a CPU-bound binary and misclassifying it would starve GPU capacity
    for plugins that actually need it."""
    body = client.get("/plugins/").json()
    ctf = next(e for e in body if e["plugin_id"] == "ctf/ctffind")
    assert "cpu_intensive" in ctf["capabilities"]
    assert "gpu_required" not in ctf["capabilities"]
    assert ctf["isolation"] == "in_process"


@pytest.mark.characterization
def test_plugin_manifest_endpoint_round_trips(client):
    """The /manifest endpoint returns the full PluginManifest. Same
    shape a remote/containerized plugin will eventually serve, so the
    manager can consume in-house and remote plugins through one model."""
    resp = client.get("/plugins/pp/template-picker/manifest")
    assert resp.status_code == 200
    m = resp.json()
    assert m["info"]["name"] == "template-picker"
    assert "resources" in m
    assert m["resources"]["memory_mb"] == 2_000
    assert m["resources"]["cpu_cores"] == 2
    assert m["isolation"] == "in_process"
    assert "tags" in m


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


# ---------------------------------------------------------------------------
# X.1 — capabilities endpoint
# ---------------------------------------------------------------------------
#
# These tests inject live entries into the singleton liveness registry
# directly, then call the endpoint, then clean up. The capabilities
# endpoint reads the registry + state store at request time, so this
# is the same shape a real plugin's announce would produce.

import pytest as _pytest

from core.plugin_liveness_registry import PluginLivenessRegistry, get_registry
from core.plugin_state import get_state_store
from magellon_sdk.discovery import Announce
from magellon_sdk.models.manifest import (
    Capability as _Cap,
    PluginManifest as _PluginManifest,
    Transport as _Transport,
)
from magellon_sdk.models.plugin import PluginInfo as _PluginInfo


def _make_announce(*, plugin_id: str, category: str, backend_id: str,
                   version: str = "1.0", instance: str = "i-1",
                   task_queue: str = None) -> Announce:
    return Announce(
        plugin_id=plugin_id,
        plugin_version=version,
        category=category,
        instance_id=instance,
        manifest=_PluginManifest(
            info=_PluginInfo(name=plugin_id, version=version, description="t"),
            backend_id=backend_id,
            capabilities=[_Cap.CPU_INTENSIVE],
            supported_transports=[_Transport.RMQ],
            default_transport=_Transport.RMQ,
        ),
        backend_id=backend_id,
        task_queue=task_queue,
    )


@_pytest.fixture
def isolated_liveness_registry(monkeypatch):
    """Swap the process-wide liveness registry singleton for a clean
    per-test instance so tests can inject entries without leaking
    across tests."""
    fresh = PluginLivenessRegistry(stale_after_seconds=300)
    monkeypatch.setattr(
        "core.plugin_liveness_registry._REGISTRY", fresh, raising=False,
    )
    # Mirror in the SDK module — controller.py reads through it.
    monkeypatch.setattr(
        "magellon_sdk.bus.services.liveness_registry._REGISTRY", fresh,
        raising=False,
    )
    return fresh


@_pytest.mark.characterization
def test_capabilities_endpoint_returns_categories_with_no_backends(
    client, isolated_liveness_registry,
):
    """With no live broker plugins, every known category still appears
    — backends list is empty, schemas still embedded. UI uses this to
    render an empty-state."""
    resp = client.get("/plugins/capabilities")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "sdk_version" in body
    cats = {c["name"] for c in body["categories"]}
    # All known categories surface, regardless of liveness.
    assert {"CTF", "MotionCor", "FFT"}.issubset(cats)
    # Every category embeds its schema for UI form rendering.
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    assert ctf["input_schema"] is not None
    assert ctf["output_schema"] is not None


@_pytest.mark.characterization
def test_capabilities_endpoint_groups_replicas_by_backend_id(
    client, isolated_liveness_registry,
):
    """Two announces with the same plugin_id under different
    instance_ids are scale-out replicas of one backend. The endpoint
    must collapse them into one ``backends[]`` row with ``live_replicas=2``,
    not show two duplicate rows."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        instance="i-1", task_queue="ctf_q",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        instance="i-2", task_queue="ctf_q",
    ))

    body = client.get("/plugins/capabilities").json()
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    backends = [b for b in ctf["backends"] if b["backend_id"] == "ctffind4"]
    assert len(backends) == 1
    assert backends[0]["live_replicas"] == 2
    assert backends[0]["task_queue"] == "ctf_q"


@_pytest.mark.characterization
def test_capabilities_endpoint_lists_distinct_backends_separately(
    client, isolated_liveness_registry,
):
    """Two distinct backends (ctffind4, gctf) under one category must
    both appear, each as its own row, so the UI can render a backend
    picker."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        task_queue="ctf_ctffind4_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-gctf", category="ctf", backend_id="gctf",
        task_queue="ctf_gctf_q", instance="i-2",
    ))

    body = client.get("/plugins/capabilities").json()
    ctf = next(c for c in body["categories"] if c["name"] == "CTF")
    backend_ids = {b["backend_id"] for b in ctf["backends"]}
    assert {"ctffind4", "gctf"}.issubset(backend_ids)


@_pytest.mark.characterization
def test_capabilities_endpoint_sorts_backends_default_first_then_alpha(
    client, isolated_liveness_registry,
):
    """X.9: ``backends[]`` ordering is part of the contract — UI
    renders the list directly without re-sorting. Default-flagged
    backend is index 0; remaining backends sort alphabetically by
    backend_id."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-zzz-engine", category="ctf", backend_id="zzz",
        task_queue="ctf_zzz_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-aaa-engine", category="ctf", backend_id="aaa",
        task_queue="ctf_aaa_q", instance="i-2",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-mmm-engine", category="ctf", backend_id="mmm",
        task_queue="ctf_mmm_q", instance="i-3",
    ))
    # Pin mmm as the default — it should come first regardless of
    # alphabetical position.
    get_state_store().set_default("ctf", "ctf-mmm-engine")
    try:
        body = client.get("/plugins/capabilities").json()
        ctf = next(c for c in body["categories"] if c["name"] == "CTF")
        backend_ids = [b["backend_id"] for b in ctf["backends"]]
        # Default first, then the remaining two in alpha order.
        assert backend_ids[0] == "mmm"
        assert backend_ids[1:] == ["aaa", "zzz"]
        assert ctf["backends"][0]["is_default_for_category"] is True
    finally:
        get_state_store().set_default("ctf", None)


@_pytest.mark.characterization
def test_capabilities_endpoint_marks_default_backend(
    client, isolated_liveness_registry, monkeypatch,
):
    """When the operator has pinned a default impl for a category, the
    endpoint must reflect both ``default_backend`` at the category
    level and ``is_default_for_category`` on the matching backend row.
    UI uses this to render the 'Default' badge."""
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-ctffind4", category="ctf", backend_id="ctffind4",
        task_queue="ctf_q", instance="i-1",
    ))
    isolated_liveness_registry.record_announce(_make_announce(
        plugin_id="ctf-gctf", category="ctf", backend_id="gctf",
        task_queue="ctf_gctf_q", instance="i-2",
    ))
    # Pin ctffind4 as the default — the same path
    # POST /plugins/categories/{cat}/default takes.
    get_state_store().set_default("ctf", "ctf-ctffind4")
    try:
        body = client.get("/plugins/capabilities").json()
        ctf = next(c for c in body["categories"] if c["name"] == "CTF")
        assert ctf["default_backend"] == "ctf-ctffind4"
        ctffind4 = next(b for b in ctf["backends"] if b["backend_id"] == "ctffind4")
        gctf = next(b for b in ctf["backends"] if b["backend_id"] == "gctf")
        assert ctffind4["is_default_for_category"] is True
        assert gctf["is_default_for_category"] is False
    finally:
        # Don't leak the pinned default into other tests.
        get_state_store().set_default("ctf", None)


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

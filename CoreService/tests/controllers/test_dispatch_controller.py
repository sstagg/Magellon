"""Tests for the generic /dispatch/{category}/* surface (PT-6).

Stubs ``services.sync_dispatcher.dispatch_capability`` so the
controller is tested in isolation. Pins:

  - 404 on unknown category
  - 422 on input that doesn't validate against the category contract
  - 503 on BackendNotLive / CapabilityMissing
  - upstream status preserved on PluginCallFailed
  - body forwarded to dispatch_capability unchanged
  - target_backend query param plumbed through
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.dispatch_controller import dispatch_router
from magellon_sdk.models.manifest import Capability
from services.sync_dispatcher import (
    BackendNotLive,
    CapabilityMissing,
    PluginCallFailed,
)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dispatch_router, prefix="/dispatch")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------


def test_run_unknown_category_404s(client):
    resp = client.post("/dispatch/never_seen_this_category/run", json={})
    assert resp.status_code == 404
    assert "Unknown category" in resp.json()["detail"]


def test_run_existing_category_validates_input(client):
    """particle_picking's input_model is CryoEmImageInput; type
    mismatches should 422 instead of getting forwarded to a plugin."""
    # image_path expects str-or-null; an int forces a TypeError.
    resp = client.post(
        "/dispatch/particle_picking/run",
        json={"image_path": 12345, "engine_opts": {}},
    )
    assert resp.status_code == 422
    assert "Invalid input" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Run / preview / retune dispatch
# ---------------------------------------------------------------------------


_VALID_BODY = {
    "image_path": "/tmp/img.mrc",
    "engine_opts": {
        "templates": ["/tmp/t.mrc"],
        "diameter_angstrom": 100.0,
        "pixel_size_angstrom": 1.0,
    },
}


def test_run_forwards_body_to_dispatcher(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={"num_particles": 7},
    ) as mock_dispatch:
        resp = client.post("/dispatch/particle_picking/run", json=_VALID_BODY)

    assert resp.status_code == 200
    assert resp.json() == {"num_particles": 7}
    mock_dispatch.assert_called_once()
    call_kwargs = mock_dispatch.call_args.kwargs
    args = mock_dispatch.call_args.args
    # signature: dispatch_capability(category, cap, method, path, *, body=, target_backend=)
    assert args[0] == "particle_picking"
    assert args[1] == Capability.SYNC
    assert args[2] == "POST"
    assert args[3] == "/execute"
    assert call_kwargs["body"] == _VALID_BODY


def test_run_with_target_backend_pin(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={},
    ) as mock_dispatch:
        client.post(
            "/dispatch/particle_picking/run?target_backend=alt-picker",
            json=_VALID_BODY,
        )
    assert mock_dispatch.call_args.kwargs["target_backend"] == "alt-picker"


def test_preview_routes_to_preview_capability(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={"preview_id": "p-1", "particles": [], "num_particles": 0,
                       "num_templates": 1, "target_pixel_size": 1.0,
                       "image_binning": 1},
    ) as mock_dispatch:
        resp = client.post("/dispatch/particle_picking/preview", json=_VALID_BODY)

    assert resp.status_code == 200
    args = mock_dispatch.call_args.args
    assert args[1] == Capability.PREVIEW
    assert args[2] == "POST"
    assert args[3] == "/preview"


def test_retune_does_not_re_validate_input(client):
    """Retune body is the params shape, not the category's input_model.
    Passing arbitrary JSON should reach the dispatcher unchanged."""
    retune_body = {"threshold": 0.5, "max_peaks": 100}
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={"particles": [], "num_particles": 0},
    ) as mock_dispatch:
        resp = client.post(
            "/dispatch/particle_picking/preview/p-1/retune", json=retune_body,
        )
    assert resp.status_code == 200
    args = mock_dispatch.call_args.args
    assert args[3] == "/preview/p-1/retune"
    assert mock_dispatch.call_args.kwargs["body"] == retune_body


def test_preview_delete_routes_to_capability(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={"deleted": True},
    ) as mock_dispatch:
        resp = client.delete("/dispatch/particle_picking/preview/p-1")
    assert resp.status_code == 200
    args = mock_dispatch.call_args.args
    assert args[2] == "DELETE"
    assert args[3] == "/preview/p-1"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_dispatch_503s_when_backend_not_live(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        side_effect=BackendNotLive("no live picker"),
    ):
        resp = client.post("/dispatch/particle_picking/run", json=_VALID_BODY)
    assert resp.status_code == 503
    assert "no live picker" in resp.json()["detail"]


def test_dispatch_503s_when_capability_missing(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        side_effect=CapabilityMissing("plugin doesn't advertise sync"),
    ):
        resp = client.post("/dispatch/particle_picking/run", json=_VALID_BODY)
    assert resp.status_code == 503


def test_dispatch_preserves_upstream_status_on_plugin_call_failed(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        side_effect=PluginCallFailed(
            status_code=404, detail={"detail": "preview expired"},
            plugin_id="x", path="/preview/p-1/retune",
        ),
    ):
        resp = client.post(
            "/dispatch/particle_picking/preview/p-1/retune",
            json={"threshold": 0.5},
        )
    assert resp.status_code == 404
    assert resp.json()["detail"] == {"detail": "preview expired"}


# ---------------------------------------------------------------------------
# Per-call timeouts
# ---------------------------------------------------------------------------


def test_retune_uses_short_timeout(client):
    """Retune is interactive (sub-100ms typical). 60s default would
    let a hung plugin block a UI tick. Pin the short timeout."""
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={"particles": [], "num_particles": 0},
    ) as mock_dispatch:
        client.post(
            "/dispatch/particle_picking/preview/p-1/retune",
            json={"threshold": 0.5},
        )
    assert mock_dispatch.call_args.kwargs["timeout_seconds"] == 5.0


def test_preview_uses_medium_timeout(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={
            "preview_id": "p-1", "particles": [], "num_particles": 0,
            "num_templates": 1, "target_pixel_size": 1.0, "image_binning": 1,
        },
    ) as mock_dispatch:
        client.post("/dispatch/particle_picking/preview", json=_VALID_BODY)
    assert mock_dispatch.call_args.kwargs["timeout_seconds"] == 30.0


def test_run_uses_full_timeout(client):
    with patch(
        "controllers.dispatch_controller.dispatch_capability",
        return_value={},
    ) as mock_dispatch:
        client.post("/dispatch/particle_picking/run", json=_VALID_BODY)
    assert mock_dispatch.call_args.kwargs["timeout_seconds"] == 60.0


# ---------------------------------------------------------------------------
# /dispatch/capabilities introspection
# ---------------------------------------------------------------------------


def test_capabilities_lists_every_known_category(client):
    """Every CategoryContract is exposed, even ones without a live
    plugin (so the React UI can render a "no backend" state)."""
    with patch(
        "core.plugin_liveness_registry.get_registry",
        return_value=type("R", (), {"list_live": lambda self: []})(),
    ), patch(
        "core.plugin_state.get_state_store",
        return_value=type("S", (), {"get_default": lambda self, c: None})(),
    ):
        resp = client.get("/dispatch/capabilities")
    assert resp.status_code == 200
    cats = {c["category"] for c in resp.json()["categories"]}
    # PARTICLE_PICKING + the rest of the canonical catalog.
    assert "particle_picking" in cats


def test_capabilities_reports_supports_flags_from_live_plugin():
    """A category's supports_sync / supports_preview flips True only
    when the default plugin both advertises the capability AND
    announced an http_endpoint. Pinned because either alone isn't
    actionable from CoreService."""
    from controllers.dispatch_controller import dispatch_router

    # Synthetic live entry advertising SYNC + PREVIEW.
    live_entry = type("E", (), {
        "plugin_id": "Template Picker",
        "category": "particle_picking",
        "http_endpoint": "http://plugin.test:8000",
        "manifest": type("M", (), {
            "capabilities": [Capability.SYNC, Capability.PREVIEW],
        })(),
    })()

    fake_registry = type("R", (), {"list_live": lambda self: [live_entry]})()
    fake_state = type("S", (), {
        "get_default": lambda self, c: "Template Picker" if c == "particle_picking" else None,
    })()

    app = FastAPI()
    app.include_router(dispatch_router, prefix="/dispatch")
    test_client = TestClient(app)

    with patch(
        "core.plugin_liveness_registry.get_registry",
        return_value=fake_registry,
    ), patch(
        "core.plugin_state.get_state_store",
        return_value=fake_state,
    ):
        body = test_client.get("/dispatch/capabilities").json()

    pp = next(c for c in body["categories"] if c["category"] == "particle_picking")
    assert pp["supports_sync"] is True
    assert pp["supports_preview"] is True
    assert pp["http_endpoint"] == "http://plugin.test:8000"
    assert pp["live_plugin_id"] == "Template Picker"


def test_capabilities_supports_flags_false_when_http_endpoint_missing():
    """A plugin that advertises PREVIEW but didn't announce
    http_endpoint can't be reached over HTTP — supports_preview must
    report False so the UI doesn't render preview controls that 503."""
    from controllers.dispatch_controller import dispatch_router

    live_entry = type("E", (), {
        "plugin_id": "p",
        "category": "particle_picking",
        "http_endpoint": None,  # plugin advertises PREVIEW but no HTTP
        "manifest": type("M", (), {"capabilities": [Capability.PREVIEW]})(),
    })()

    app = FastAPI()
    app.include_router(dispatch_router, prefix="/dispatch")
    test_client = TestClient(app)

    with patch(
        "core.plugin_liveness_registry.get_registry",
        return_value=type("R", (), {"list_live": lambda self: [live_entry]})(),
    ), patch(
        "core.plugin_state.get_state_store",
        return_value=type("S", (), {"get_default": lambda self, c: None})(),
    ):
        body = test_client.get("/dispatch/capabilities").json()

    pp = next(c for c in body["categories"] if c["category"] == "particle_picking")
    assert pp["supports_preview"] is False

"""Contract pin for the /particle-picking/* surface.

Smoke test that the router registers the right paths. Compute
behaviour is covered by ``tests/test_template_picker.py``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from config import app_settings
from controllers.particle_picking_controller import (
    PreviewRequest,
    _calibrate_topaz_from_annotations,
    list_pp_backends,
    _preview_payload,
    _resolve_pp_category,
    particle_picking_router,
    template_pick_preview,
)
from magellon_sdk.models.manifest import Capability


def _route_paths(router) -> set[str]:
    return {r.path for r in router.routes}


def test_router_exposes_clean_paths():
    """One path per particle-picking feature; no legacy
    ``/template-pick/`` segments after PI-5."""
    expected = {
        "/",
        "/preview",
        "/preview/{preview_id}/retune",
        "/preview/{preview_id}",
        "/async",
        "/jobs",
        "/jobs/{job_id}",
        "/info",
        "/health",
        "/requirements",
        "/schema/input",
        "/schema/output",
        "/session-images",
        "/run-and-save",
        "/batch",
        "/records/{ipp_oid}/coco",
        "/topaz/session-models",
    }
    paths = _route_paths(particle_picking_router)
    missing = expected - paths
    assert not missing, f"router is missing expected paths: {missing}"


def test_no_legacy_template_pick_segments_in_paths():
    """Pin the rename: no path should contain ``template-pick`` after
    PI-5 — that segment was the in-process plugin's legacy URL shape."""
    for path in _route_paths(particle_picking_router):
        assert "template-pick" not in path, (
            f"path {path!r} still carries the legacy template-pick segment"
        )


# ---------------------------------------------------------------------------
# Backend-aware preview routing
# ---------------------------------------------------------------------------


def test_resolve_pp_category_routes_topaz_and_defaults_others():
    """Any topaz backend id routes to the topaz category; everything
    else falls through to the particle_picking category."""
    assert _resolve_pp_category(None) == "particle_picking"
    assert _resolve_pp_category("template-picker") == "particle_picking"
    assert _resolve_pp_category("boxnet-picker") == "particle_picking"
    assert _resolve_pp_category("topaz") == "topaz_particle_picking"
    assert _resolve_pp_category("topaz-particle-picking") == "topaz_particle_picking"
    assert _resolve_pp_category("topaz_particle_picking") == "topaz_particle_picking"


def test_preview_payload_topaz_nests_engine_opts():
    """Topaz preview body becomes TopazPickInput shape — flat picker
    params collapse into a nested engine_opts dict."""
    req = PreviewRequest(
        backend="topaz", image_path="/gpfs/x.mrc",
        model="resnet8", threshold=-2.5, radius=18, scale=8,
    )
    payload = _preview_payload(req, is_topaz=True)
    assert payload["input_file"] == "/gpfs/x.mrc"
    assert payload["engine_opts"] == {
        "model": "resnet8", "threshold": -2.5, "radius": 18, "scale": 8,
    }
    # routing fields never leak into the engine knobs
    assert "backend" not in payload["engine_opts"]
    assert "image_path" not in payload["engine_opts"]


def test_preview_payload_template_picker_validates_strict_input():
    """Non-topaz preview re-validates against TemplatePickerInput and
    strips the routing-only fields TemplatePickerInput would forbid."""
    req = PreviewRequest(
        backend="template-picker", image_path="/gpfs/x.mrc",
        session_name="24dec03a", template_paths=["/gpfs/t1.mrc"], threshold=0.4,
    )
    payload = _preview_payload(req, is_topaz=False)
    assert payload["image_path"] == "/gpfs/x.mrc"
    assert payload["template_paths"] == ["/gpfs/t1.mrc"]
    assert "backend" not in payload and "session_name" not in payload


def test_preview_payload_template_picker_resolves_ui_image_name(monkeypatch):
    """The React panel sends image name + session, not a server path.
    Preview must resolve that to the raw MRC path for Docker plugins."""
    monkeypatch.setattr(
        app_settings.directory_settings,
        "MAGELLON_HOME_DIR",
        "/gpfs",
    )
    req = PreviewRequest(
        backend="template-picker",
        image_path="24dec03a_00031gr_00001sq_v01_00002hl_00001fc",
        session_name="24DEC03A",
        template_paths=["/gpfs/t1.mrc"],
        threshold=0.4,
    )
    payload = _preview_payload(req, is_topaz=False)
    assert payload["image_path"] == (
        "/gpfs/24dec03a/original/"
        "24dec03a_00031gr_00001sq_v01_00002hl_00001fc.mrc"
    )


def test_preview_payload_template_picker_rejects_bad_input():
    """A template-picker body that violates the strict model raises —
    the endpoint maps that to a 422."""
    req = PreviewRequest(
        backend="template-picker", image_path="/gpfs/x.mrc", template_paths=[],
    )
    with pytest.raises(ValidationError):
        _preview_payload(req, is_topaz=False)


def test_preview_payload_boxnet_uses_plugin_owned_input_shape():
    """BoxNet has no template_paths; its plugin-owned schema validates
    threshold/min_distance/invert on the plugin side."""
    req = PreviewRequest(
        backend="boxnet-picker",
        image_path="/gpfs/x.mrc",
        threshold=0.3,
        min_distance=14,
        scale=8,
        invert=True,
    )

    payload = _preview_payload(req, is_topaz=False)

    assert payload == {
        "image_path": "/gpfs/x.mrc",
        "threshold": 0.3,
        "min_distance": 14,
        "scale": 8,
        "invert": True,
    }


@pytest.mark.asyncio
async def test_preview_dispatch_pins_selected_boxnet_backend(monkeypatch):
    """A preview-capable BoxNet must not resolve to the category-default
    template-picker just because both share particle_picking."""
    calls = {}

    def fake_dispatch(category, capability, method, path, *, body=None, target_backend=None):
        calls.update(
            category=category,
            capability=capability,
            method=method,
            path=path,
            body=body,
            target_backend=target_backend,
        )
        return {
            "preview_id": "pv-boxnet",
            "particles": [],
            "num_particles": 0,
            "num_templates": 0,
            "target_pixel_size": 8.0,
            "image_binning": 8,
            "image_shape": [16, 16],
        }

    monkeypatch.setattr(
        "controllers.particle_picking_controller.dispatch_capability",
        fake_dispatch,
    )

    result = await template_pick_preview(
        PreviewRequest(
            backend="boxnet-picker",
            image_path="/gpfs/x.mrc",
            threshold=0.3,
        )
    )

    assert result.preview_id == "pv-boxnet"
    assert calls["category"] == "particle_picking"
    assert calls["capability"] is Capability.PREVIEW
    assert calls["target_backend"] == "boxnet-picker"
    assert calls["body"]["threshold"] == 0.3


@pytest.mark.asyncio
async def test_backends_prefers_announced_metadata_over_heartbeat_stub(monkeypatch):
    """Heartbeat stubs can arrive before announce metadata. The UI must
    see the richer entry so Preview & Tune stays enabled."""
    stub = SimpleNamespace(
        backend_id="template-picker",
        plugin_id="Template Picker",
        category="particle picking",
        manifest=None,
        http_endpoint=None,
        status="ready",
    )
    rich = SimpleNamespace(
        backend_id="template-picker",
        plugin_id="Template Picker",
        category="particle picking",
        manifest=SimpleNamespace(
            capabilities=[Capability.SYNC, Capability.PREVIEW],
            info=SimpleNamespace(name="Template Picker"),
        ),
        http_endpoint="http://127.0.0.1:18001/",
        status="ready",
    )
    registry = SimpleNamespace(list_live=lambda: [stub, rich])
    monkeypatch.setattr(
        "controllers.particle_picking_controller.get_liveness_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "controllers.particle_picking_controller.get_state_store",
        lambda: SimpleNamespace(is_enabled=lambda plugin_id: True),
    )

    body = await list_pp_backends()

    assert body == [{
        "backend_id": "template-picker",
        "plugin_id": "Template Picker",
        "label": "Template Picker",
        "capabilities": ["sync", "preview"],
        "has_preview": True,
        "has_sync": True,
        "http_endpoint": "http://127.0.0.1:18001/",
        "status": "ready",
        "enabled": True,
    }]


def test_topaz_session_calibration_uses_annotation_scores():
    engine_opts, diagnostics = _calibrate_topaz_from_annotations(
        annotations=[
            {"x": 100, "y": 100, "radius": 80, "class": "1", "type": "manual"},
            {"x": 300, "y": 300, "radius": 80, "class": "3", "type": "manual"},
        ],
        candidates=[
            {"x": 104, "y": 98, "score": -1.0, "radius": 80},
            {"x": 302, "y": 296, "score": -4.0, "radius": 80},
            {"x": 800, "y": 800, "score": 2.0, "radius": 80},
        ],
        picker_params={"model": "resnet16", "scale": 8, "threshold": -3.0},
        positive_classes=["1"],
        negative_classes=["2", "3"],
    )

    assert engine_opts["radius"] == 10
    assert engine_opts["threshold"] == pytest.approx(-1.25)
    assert engine_opts["session_training_method"] == "topaz_score_calibration"
    assert diagnostics["matched_positive"] == 1
    assert diagnostics["matched_negative"] == 1

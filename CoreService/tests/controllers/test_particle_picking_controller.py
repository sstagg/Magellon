"""Contract pin for the /particle-picking/* surface.

Smoke test that the router registers the right paths. Compute
behaviour is covered by ``tests/test_template_picker.py``.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from controllers.particle_picking_controller import (
    PreviewRequest,
    _preview_payload,
    _resolve_pp_category,
    particle_picking_router,
)


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


def test_preview_payload_template_picker_rejects_bad_input():
    """A template-picker body that violates the strict model raises —
    the endpoint maps that to a 422."""
    req = PreviewRequest(
        backend="template-picker", image_path="/gpfs/x.mrc", template_paths=[],
    )
    with pytest.raises(ValidationError):
        _preview_payload(req, is_topaz=False)

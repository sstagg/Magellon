"""Contract pin for the /particle-picking/* surface.

Smoke test that the router registers the right paths. Compute
behaviour is covered by ``tests/test_template_picker.py``.
"""
from __future__ import annotations

from controllers.particle_picking_controller import particle_picking_router


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

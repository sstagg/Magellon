"""PI-4: contract pin for the new /particle-picking/* surface.

Doesn't exercise the actual compute (that's covered by
test_template_picker.py); this is a smoke test that the new router
registers the right paths against the right handlers, and that the
old ``/plugins/pp/template-pick/*`` URLs still work alongside.
"""
from __future__ import annotations

from controllers.particle_picking_controller import particle_picking_router
from plugins.pp.controller import pp_router


def _route_paths(router) -> set[str]:
    return {r.path for r in router.routes}


# ---------------------------------------------------------------------------
# Path inventory — pin the URL contract
# ---------------------------------------------------------------------------


def test_new_router_exposes_clean_paths():
    """Each old ``/template-pick/...`` path has a clean equivalent
    on the new router. PI-5 deletes the old; until then both are live."""
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
    assert not missing, f"new router is missing expected paths: {missing}"


def test_new_router_handlers_are_same_objects_as_pp_router():
    """No code duplication: new routes wrap the SAME handler functions
    pp_router does. Pinned because future drift between the two would
    mean the new and old URLs return different things."""
    pp_endpoints_by_name = {
        r.endpoint.__name__: r.endpoint
        for r in pp_router.routes
        if hasattr(r, "endpoint")
    }
    for route in particle_picking_router.routes:
        if not hasattr(route, "endpoint"):
            continue
        name = route.endpoint.__name__
        if name in pp_endpoints_by_name:
            assert route.endpoint is pp_endpoints_by_name[name], (
                f"handler {name} is a different object on the new router — "
                f"someone re-implemented instead of re-registering"
            )


def test_old_pp_router_routes_still_present():
    """Back-compat invariant: PI-4 must NOT remove any old routes.
    PI-5 will. Surfaces accidental deletion early."""
    old_paths = _route_paths(pp_router)
    expected_old = {
        "/template-pick",
        "/template-pick/preview",
        "/template-pick/preview/{preview_id}",
        "/template-pick/preview/{preview_id}/retune",
        "/template-pick-async",
        "/jobs",
        "/jobs/{job_id}",
        "/template-pick/info",
        "/template-pick/health",
        "/template-pick/requirements",
        "/template-pick/schema/input",
        "/template-pick/schema/output",
        "/template-pick/session-images",
        "/template-pick/run-and-save",
        "/template-pick/batch",
        "/template-pick/records/{ipp_oid}/coco",
    }
    missing = expected_old - old_paths
    assert not missing, f"old pp_router lost paths in PI-4: {missing}"

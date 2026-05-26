from __future__ import annotations

from controllers.webapp_controller import webapp_router


def test_webapp_router_does_not_expose_casbin_debug_route():
    paths = {route.path for route in webapp_router.routes}

    assert "/debug/casbin-check" not in paths

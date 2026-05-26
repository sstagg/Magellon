from __future__ import annotations

from controllers.db_controller import db_router


def _methods_for(path: str) -> set[str]:
    methods: set[str] = set()
    for route in db_router.routes:
        if getattr(route, "path", None) == path:
            methods.update(getattr(route, "methods", set()))
    return methods


def test_database_router_exposes_create_but_not_drop():
    methods = _methods_for("/database")

    assert "POST" in methods
    assert "DELETE" not in methods

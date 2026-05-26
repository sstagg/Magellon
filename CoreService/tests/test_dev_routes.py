from __future__ import annotations

from fastapi import FastAPI

from core.dev_routes import dev_routes_enabled, register_dev_routes


def test_dev_routes_disabled_by_default():
    assert dev_routes_enabled({}) is False


def test_dev_routes_accept_explicit_truthy_values():
    for value in ("1", "true", "TRUE", "yes", "on"):
        assert dev_routes_enabled({"MAGELLON_ENABLE_DEV_ROUTES": value}) is True


def test_dev_routes_reject_non_truthy_values():
    for value in ("", "0", "false", "no", "off", "dev"):
        assert dev_routes_enabled({"MAGELLON_ENABLE_DEV_ROUTES": value}) is False


def test_test_and_rls_routes_are_not_mounted_by_default(monkeypatch):
    monkeypatch.delenv("MAGELLON_ENABLE_DEV_ROUTES", raising=False)

    from main import app

    paths = {route.path for route in app.routes}
    assert "/test/parse-xml" not in paths
    assert "/test-rls/grant-access" not in paths
    assert "/test-rls/sessions/all" not in paths


def test_register_dev_routes_mounts_single_prefix_paths():
    app = FastAPI()

    register_dev_routes(app)

    paths = {route.path for route in app.routes}
    assert "/test/parse-xml" in paths
    assert "/test/test/parse-xml" not in paths
    assert "/test-rls/grant-access" in paths

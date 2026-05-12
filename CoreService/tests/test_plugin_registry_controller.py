"""HTTP-layer tests for the PE4 plugin-registry merge endpoint.

Mounts the router on a throwaway FastAPI app so the test doesn't drag
in DB/RMQ startup. ``httpx.get`` is patched so we control the hub
response without a network.

What we pin:

  - Hub fetch + merge: every hub plugin lands in the response.
  - Installed plugin shows ``installed_version`` + ``update_available``.
  - Local-only plugins (installed but absent from the hub) surface
    with ``source="local-only"``.
  - Hub 5xx / unreachable / non-JSON degrade to ``hub_status != "ok"``
    without crashing the endpoint.
  - Version comparison uses lenient SemVer-style ordering.
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import plugin_registry_controller as ctl
from dependencies.permissions import require_role
from services.plugin_catalog_persistence import get_plugin_catalog_persistence


@pytest.fixture
def fake_catalog():
    return MagicMock()


@pytest.fixture
def client(fake_catalog):
    app = FastAPI()
    app.include_router(ctl.plugin_registry_router, prefix="/plugins/registry")
    app.dependency_overrides[get_plugin_catalog_persistence] = lambda: fake_catalog
    app.dependency_overrides[require_role("Administrator")] = lambda: None
    # Bind every require_role dependency to a passthrough.
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for dep in dependant.dependencies:
                if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                    app.dependency_overrides[dep.call] = lambda: None
    return TestClient(app)


def _hub_response(body: Dict[str, Any], status_code: int = 200):
    class R:
        def __init__(self):
            self.status_code = status_code
            self.text = ""

        def json(self):
            return body

    return R()


# ---------------------------------------------------------------------------
# Happy path: merge hub + local state
# ---------------------------------------------------------------------------


class TestMergeBehaviour:
    def test_lists_hub_plugins(self, client, fake_catalog, monkeypatch):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({
            "plugins": [
                {
                    "slug": "fft-classical",
                    "display_name": "Classical FFT",
                    "category": "fft",
                    "versions": [{"version": "1.0.0", "archive_url": "https://hub/x"}],
                },
            ],
        }))
        resp = client.get("/plugins/registry/index")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hub_status"] == "ok"
        assert len(body["plugins"]) == 1
        assert body["plugins"][0]["plugin_id"] == "fft-classical"
        assert body["plugins"][0]["latest_hub_version"] == "1.0.0"
        assert body["plugins"][0]["installed_version"] is None
        assert body["plugins"][0]["update_available"] is False

    def test_installed_with_update_available(self, client, fake_catalog, monkeypatch):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[
            {"manifest_plugin_id": "fft-classical", "version": "0.9.0", "install_method": "uv"},
        ])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({
            "plugins": [
                {
                    "slug": "fft-classical",
                    "display_name": "Classical FFT",
                    "versions": [{"version": "1.0.0"}],
                },
            ],
        }))
        body = client.get("/plugins/registry/index").json()
        plugin = body["plugins"][0]
        assert plugin["installed_version"] == "0.9.0"
        assert plugin["install_method"] == "uv"
        assert plugin["update_available"] is True

    def test_installed_at_latest_no_update_available(self, client, fake_catalog, monkeypatch):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[
            {"manifest_plugin_id": "fft-classical", "version": "1.0.0", "install_method": "uv"},
        ])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({
            "plugins": [
                {"slug": "fft-classical", "display_name": "Classical FFT",
                 "versions": [{"version": "1.0.0"}]},
            ],
        }))
        plugin = client.get("/plugins/registry/index").json()["plugins"][0]
        assert plugin["installed_version"] == "1.0.0"
        assert plugin["update_available"] is False

    def test_local_only_plugin_surfaces_with_source_tag(self, client, fake_catalog, monkeypatch):
        """A locally-installed plugin that the hub doesn't know about
        (air-gapped / custom) shows up with ``source="local-only"``."""
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[
            {"manifest_plugin_id": "in-house-tool", "version": "0.1.0", "install_method": "uv"},
        ])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({
            "plugins": [],
        }))
        body = client.get("/plugins/registry/index").json()
        # Hub plugin list is empty; the local-only plugin still appears.
        assert len(body["plugins"]) == 1
        assert body["plugins"][0]["plugin_id"] == "in-house-tool"
        assert body["plugins"][0]["source"] == "local-only"


# ---------------------------------------------------------------------------
# Hub degradation
# ---------------------------------------------------------------------------


class TestHubDegradation:
    def test_hub_5xx_yields_hub_status_http_5xx(self, client, fake_catalog, monkeypatch):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({}, status_code=500))
        body = client.get("/plugins/registry/index").json()
        assert body["hub_status"] == "http_500"
        # Endpoint still returns 200 — local-only path still works.
        assert body["plugins"] == []

    def test_hub_unreachable_returns_empty_hub_plugins(self, client, fake_catalog, monkeypatch):
        import httpx

        def boom(*_a, **_kw):
            raise httpx.ConnectError("no route to hub")

        fake_catalog.list_installed_with_versions = MagicMock(return_value=[])
        monkeypatch.setattr("httpx.get", boom)
        body = client.get("/plugins/registry/index").json()
        assert body["hub_status"] == "unreachable"
        assert body["hub_error"]
        assert body["plugins"] == []

    def test_hub_returns_non_json_degrades(self, client, fake_catalog, monkeypatch):
        class _NotJsonResp:
            status_code = 200
            text = "this is not json"

            def json(self):
                raise ValueError("not json")

        fake_catalog.list_installed_with_versions = MagicMock(return_value=[])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _NotJsonResp())
        body = client.get("/plugins/registry/index").json()
        assert body["hub_status"] == "unreachable"


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


class TestVersionComparison:
    @pytest.mark.parametrize("installed,latest,expected_update", [
        ("0.9.0", "1.0.0", True),
        ("1.0.0", "1.0.1", True),
        ("2.0.0", "1.9.9", False),
        ("1.0.0", "1.0.0", False),
    ])
    def test_update_available_flag(
        self, client, fake_catalog, monkeypatch, installed, latest, expected_update,
    ):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[
            {"manifest_plugin_id": "p", "version": installed, "install_method": "uv"},
        ])
        monkeypatch.setattr("httpx.get", lambda *_a, **_kw: _hub_response({
            "plugins": [
                {"slug": "p", "display_name": "P", "versions": [{"version": latest}]},
            ],
        }))
        plugin = client.get("/plugins/registry/index").json()["plugins"][0]
        assert plugin["update_available"] is expected_update


# ---------------------------------------------------------------------------
# Hub URL override
# ---------------------------------------------------------------------------


class TestHubUrlOverride:
    def test_query_param_overrides_default_hub_url(self, client, fake_catalog, monkeypatch):
        fake_catalog.list_installed_with_versions = MagicMock(return_value=[])
        seen_urls: list[str] = []

        def capture(url, *_a, **_kw):
            seen_urls.append(url)
            return _hub_response({"plugins": []})

        monkeypatch.setattr("httpx.get", capture)
        body = client.get(
            "/plugins/registry/index",
            params={"hub_url": "https://staging.hub.example"},
        ).json()
        assert body["hub_url"] == "https://staging.hub.example"
        assert any("staging.hub.example" in url for url in seen_urls)

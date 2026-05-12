"""Security probes for the /install-from-hub endpoint.

Threat model: a hub the deployment trusts (or a MITM) could serve a
different archive than the manifest claims. The endpoint's defenses:

  - sha256 verification on the downloaded archive bytes.
  - Refusal of malformed hub JSON.
  - Hub URL is operator-supplied or defaulted; no third-party
    redirect short-circuits the verification.

What we pin:

  - sha256 mismatch → 502 (don't trust the hub).
  - Missing archive.sha256 in hub JSON → 502.
  - Hub returns 4xx/5xx → 502 (don't expose hub internals as 5xx
    from CoreService).
  - Version-not-found → 404.
  - Plugin-not-found → 404.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import admin_plugin_install_controller as ctl
from dependencies.permissions import require_role
from services.plugin_installer.factory import (
    get_install_manager,
    get_runtime_config,
)
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
)
from services.plugin_catalog_persistence import get_plugin_catalog_persistence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_manager():
    m = MagicMock()
    m.install.return_value = InstallResult(
        success=True, plugin_id="fft", install_method="uv",
        install_dir=Path("/var/magellon/plugins/installed/fft"),
    )
    return m


@pytest.fixture
def fake_catalog():
    return MagicMock()


@pytest.fixture
def fake_runtime():
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


@pytest.fixture
def client(fake_manager, fake_catalog, fake_runtime):
    app = FastAPI()
    app.include_router(ctl.admin_plugin_install_router, prefix="/admin/plugins")
    app.dependency_overrides[get_install_manager] = lambda: fake_manager
    app.dependency_overrides[get_plugin_catalog_persistence] = lambda: fake_catalog
    app.dependency_overrides[get_runtime_config] = lambda: fake_runtime
    app.dependency_overrides[require_role("Administrator")] = lambda: None
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for dep in dependant.dependencies:
                if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                    app.dependency_overrides[dep.call] = lambda: None
    return TestClient(app)


def _fake_archive_bytes() -> bytes:
    return b"fake archive content"


def _sha256_of(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# sha256 mismatch — refusal at the install boundary
# ---------------------------------------------------------------------------


class TestSha256Verification:
    def test_archive_sha256_mismatch_returns_502(self, client, monkeypatch):
        """The hub catalog claims one sha256; the archive bytes hash
        to something else. Refuse the install with 502 — we can't trust
        the source."""
        archive_bytes = _fake_archive_bytes()
        wrong_sha = "0" * 64  # known-bad

        def fake_get(url, *a, **kw):
            class R:
                status_code = 200
                content = archive_bytes
                text = ""

                def json(self):
                    return {
                        "plugin_id": "fft",
                        "versions": [{
                            "version": "1.0.0",
                            "archive": {
                                "url": "/assets/fft-1.0.0.mpn",
                                "sha256": wrong_sha,
                            },
                        }],
                    }

            return R()

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "1.0.0"},
        )

        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "sha256" in detail.lower()
        assert "mismatch" in detail.lower() or "refusing" in detail.lower()

    def test_archive_sha256_match_proceeds_to_install(
        self, client, fake_manager, monkeypatch,
    ):
        archive_bytes = _fake_archive_bytes()
        right_sha = _sha256_of(archive_bytes)

        def fake_get(url, *a, **kw):
            class R:
                status_code = 200
                content = archive_bytes
                text = ""

                def json(self):
                    return {
                        "plugin_id": "fft",
                        "versions": [{
                            "version": "1.0.0",
                            "archive": {
                                "url": "/assets/fft-1.0.0.mpn",
                                "sha256": right_sha,
                            },
                        }],
                    }

            return R()

        monkeypatch.setattr("httpx.get", fake_get)
        # Also bypass the catalog-mirror side path which tries to parse
        # the archive bytes as a real .mpn.
        monkeypatch.setattr(
            "controllers.admin_plugin_install_controller._persist_to_packages_dir",
            lambda p: None,
        )

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "1.0.0"},
        )

        assert resp.status_code == 201
        fake_manager.install.assert_called_once()


# ---------------------------------------------------------------------------
# Hub JSON shape
# ---------------------------------------------------------------------------


class TestHubJsonShape:
    def test_missing_sha256_in_hub_entry_is_502(self, client, monkeypatch):
        """An archive entry missing ``sha256`` makes verification
        impossible — refuse rather than skip the check."""
        def fake_get(url, *a, **kw):
            class R:
                status_code = 200
                content = b""
                text = ""

                def json(self):
                    return {
                        "plugin_id": "fft",
                        "versions": [{
                            "version": "1.0.0",
                            "archive": {"url": "/x.mpn"},  # no sha256
                        }],
                    }

            return R()

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "1.0.0"},
        )

        assert resp.status_code == 502

    def test_unknown_version_is_404(self, client, monkeypatch):
        def fake_get(url, *a, **kw):
            class R:
                status_code = 200
                content = b""
                text = ""

                def json(self):
                    return {
                        "plugin_id": "fft",
                        "versions": [{
                            "version": "0.9.0",
                            "archive": {"url": "/x.mpn", "sha256": "0" * 64},
                        }],
                    }

            return R()

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "99.0.0"},
        )

        assert resp.status_code == 404
        assert "99.0.0" in resp.json()["detail"]

    def test_unknown_plugin_is_404(self, client, monkeypatch):
        def fake_get(url, *a, **kw):
            class R:
                status_code = 404
                content = b""
                text = "not found"

                def json(self):
                    return {}

            return R()

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "doesnotexist", "version": "1.0.0"},
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Hub network / 5xx behaviour
# ---------------------------------------------------------------------------


class TestHubNetwork:
    def test_hub_5xx_is_502_from_us(self, client, monkeypatch):
        """The hub returning 500 must surface as 502 from CoreService —
        a hub problem is upstream, not our problem."""
        def fake_get(url, *a, **kw):
            class R:
                status_code = 500
                content = b""
                text = "boom"

                def json(self):
                    raise ValueError("not json")

            return R()

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "1.0.0"},
        )

        assert resp.status_code == 502

    def test_hub_unreachable_is_502(self, client, monkeypatch):
        import httpx

        def fake_get(url, *a, **kw):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("httpx.get", fake_get)

        resp = client.post(
            "/admin/plugins/install-from-hub",
            json={"plugin_id": "fft", "version": "1.0.0"},
        )

        assert resp.status_code == 502
        assert "unreachable" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Upload path — extension guard
# ---------------------------------------------------------------------------


class TestUploadExtensionGuard:
    def test_non_mpn_upload_returns_400(self, client):
        """Operator uploads ``foo.txt`` instead of a .mpn. Should
        refuse with a meaningful message, not surface as a manager
        error 500."""
        resp = client.post(
            "/admin/plugins/install",
            files={"file": ("evil.txt", b"not an archive")},
        )
        assert resp.status_code == 400
        assert ".mpn" in resp.json()["detail"]

    def test_missing_filename_is_rejected(self, client):
        """Empty filename — either the FastAPI multipart layer rejects
        it (422) or the controller does (400). Both prevent the bytes
        from reaching the manager."""
        resp = client.post(
            "/admin/plugins/install",
            files={"file": ("", b"some bytes")},
        )
        assert resp.status_code in (400, 422)

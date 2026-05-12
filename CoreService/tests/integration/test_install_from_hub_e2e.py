"""E2E pin for the Phase 4 hub-install endpoint.

POST /admin/plugins/install-from-hub fetches the .mpn from the hub,
verifies sha256 against the hub's catalog JSON, and delegates to the
existing PluginInstallManager. This test points CoreService at a
fixture-served mock hub so we exercise the full HTTP + verification +
install pipeline without depending on magellon.org or the network.

Sad paths covered:
  - sha256 mismatch → 502 ("refusing to install tampered archive")
  - version not published → 404
  - hub 5xx → 502
"""
from __future__ import annotations

import hashlib
import logging
import time

import pytest

from tests.integration._e2e_helpers.install import (
    uninstall_plugin,
    wait_for_lifecycle_status,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


def _hub_plugin_json(
    *,
    plugin_id: str,
    version: str,
    archive_filename: str,
    archive_sha256: str,
) -> dict:
    """Per-plugin JSON shape the hub publishes.

    Mirrors the Astro content collection's published structure: a
    top-level ``versions`` array, each with an ``archive`` block
    carrying ``url``, ``sha256``, ``size_bytes``.
    """
    return {
        "plugin_id": plugin_id,
        "versions": [
            {
                "version": version,
                "archive": {
                    "filename": archive_filename,
                    "url": f"/assets/plugins/{archive_filename}",
                    "sha256": archive_sha256,
                    "size_bytes": 0,  # unused by install
                },
            },
        ],
    }


def test_install_from_hub_happy_path(
    e2e_stack, admin_client, mock_hub, fft_mpn_archive,
):
    """The hub serves the real FFT archive; CoreService fetches +
    verifies + installs. Same install pipeline as the upload path —
    only the source-of-bytes differs."""
    plugin_id = "fft"
    # Clean any prior install so the install endpoint sees a fresh slate.
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)

    archive_bytes = fft_mpn_archive.read_bytes()
    archive_sha = hashlib.sha256(archive_bytes).hexdigest()
    archive_name = fft_mpn_archive.name
    # Derive version from filename: "fft-1.1.0.mpn" → "1.1.0".
    version = archive_name.removeprefix("fft-").removesuffix(".mpn")

    mock_hub.set_archive(archive_name, archive_bytes)
    mock_hub.set_plugin_json(
        plugin_id,
        _hub_plugin_json(
            plugin_id=plugin_id, version=version,
            archive_filename=archive_name, archive_sha256=archive_sha,
        ),
    )

    resp = admin_client.post(
        "/admin/plugins/install-from-hub",
        json={
            "plugin_id": plugin_id, "version": version,
            "hub_url": mock_hub.base_url,
        },
        timeout=180.0,
    )
    assert resp.status_code == 201, (
        f"install-from-hub failed: {resp.status_code} {resp.text[:400]}"
    )
    body = resp.json()
    assert body["plugin_id"] == plugin_id
    assert body["install_method"] in ("uv", "docker"), body

    # Verify the install settled before we uninstall — otherwise the
    # uninstall races the still-spawning container.
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)

    # Cleanup so subsequent tests in this run see a clean slate.
    uninstall_plugin(admin_client, plugin_id)


def test_install_from_hub_rejects_sha256_mismatch(
    e2e_stack, admin_client, mock_hub, fft_mpn_archive,
):
    """The threat model: a compromised hub serving a different archive
    under a known plugin_id+version. CoreService must refuse before
    handing bytes to the install pipeline."""
    plugin_id = "fft"
    archive_bytes = fft_mpn_archive.read_bytes()
    archive_name = fft_mpn_archive.name
    version = archive_name.removeprefix("fft-").removesuffix(".mpn")

    # Hub claims a wrong sha — install must refuse with 502.
    wrong_sha = "0" * 64
    mock_hub.set_archive(archive_name, archive_bytes)
    mock_hub.set_plugin_json(
        plugin_id,
        _hub_plugin_json(
            plugin_id=plugin_id, version=version,
            archive_filename=archive_name, archive_sha256=wrong_sha,
        ),
    )

    resp = admin_client.post(
        "/admin/plugins/install-from-hub",
        json={
            "plugin_id": plugin_id, "version": version,
            "hub_url": mock_hub.base_url,
        },
    )

    assert resp.status_code == 502, resp.text
    assert "sha256 mismatch" in resp.json()["detail"]

    # No install attempted: status should still report not installed
    # (unless an unrelated prior install is in place; we tolerate either
    # state since this test doesn't own the cleanup of a prior install).
    after = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    assert after.status_code == 200


def test_install_from_hub_404_when_version_not_published(
    e2e_stack, admin_client, mock_hub, fft_mpn_archive,
):
    """Hub knows the plugin, but the requested version isn't in its
    versions list. Surface as 404 with the available-versions detail."""
    plugin_id = "fft"
    archive_name = fft_mpn_archive.name
    # Only version "1.0.0" published; request "9.9.9".
    mock_hub.set_plugin_json(
        plugin_id,
        _hub_plugin_json(
            plugin_id=plugin_id, version="1.0.0",
            archive_filename=archive_name, archive_sha256="0" * 64,
        ),
    )

    resp = admin_client.post(
        "/admin/plugins/install-from-hub",
        json={
            "plugin_id": plugin_id, "version": "9.9.9",
            "hub_url": mock_hub.base_url,
        },
    )

    assert resp.status_code == 404, resp.text
    detail = resp.json()["detail"]
    assert "9.9.9" in detail
    # Available-versions hint must be present so operators can recover.
    assert "1.0.0" in detail or "Available" in detail


def test_install_from_hub_502_when_hub_500s(
    e2e_stack, admin_client, mock_hub,
):
    """Hub itself is unhealthy — surface as 502 (we depended on an
    upstream that failed), not 500 (CoreService itself failed)."""
    plugin_id = "fft"
    mock_hub.set_plugin_status(plugin_id, 500)

    resp = admin_client.post(
        "/admin/plugins/install-from-hub",
        json={
            "plugin_id": plugin_id, "version": "1.1.0",
            "hub_url": mock_hub.base_url,
        },
    )

    assert resp.status_code == 502, resp.text

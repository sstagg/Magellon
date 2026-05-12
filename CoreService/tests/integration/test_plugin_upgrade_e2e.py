"""E2E pin for the Phase 8/9 upgrade flow.

Install FFT v1.1.0 (from the local .mpn fixture), dispatch a task to
confirm a working baseline, then upgrade to a synthesized v1.1.1
served by the mock_hub. Assert:

  - The new install_state's version reflects v1.1.1.
  - The plugin re-announces post-upgrade.
  - Dispatch still works on the new version.

Rollback path is exercised by uninstalling at the end; the manager's
internal versioned-.bak handling is already covered at the unit level
(see test_manager_supervisor.py / test_install_lifecycle.py).
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from pathlib import Path

import pytest

from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


def _hub_plugin_json(*, plugin_id, version, archive_filename, sha256):
    return {
        "plugin_id": plugin_id,
        "versions": [
            {
                "version": version,
                "requires_sdk": ">=2.1,<3.0",
                "archive": {
                    "filename": archive_filename,
                    "url": f"/assets/plugins/{archive_filename}",
                    "sha256": sha256,
                    "size_bytes": 0,
                },
            },
        ],
    }


def _repack_with_version(source_mpn: Path, *, new_version: str,
                        out_dir: Path) -> Path:
    """Build a synthetic upgrade target by rewriting the version field
    in the .mpn's manifest.yaml / plugin.yaml. The plugin code is
    unchanged — we just need a version-monotonic install for the
    upgrade gate to accept.
    """
    import zipfile
    out = out_dir / f"fft-{new_version}.mpn"
    with zipfile.ZipFile(source_mpn) as src:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename in ("manifest.yaml", "plugin.yaml"):
                    text = data.decode("utf-8")
                    # Naive replace: the manifest has exactly one
                    # ``version: <semver>`` line. If the test fixture
                    # has aliases or pre-release suffixes, tighten this.
                    new_text_lines = []
                    for line in text.splitlines():
                        if line.startswith("version:"):
                            new_text_lines.append(f"version: {new_version}")
                        else:
                            new_text_lines.append(line)
                    data = ("\n".join(new_text_lines) + "\n").encode("utf-8")
                dst.writestr(info.filename, data)
    return out


def test_upgrade_from_hub_full_arc(
    e2e_stack, admin_client, mock_hub, fft_mpn_archive, tmp_path,
):
    """Install v1.1.0 → upgrade to v1.1.1 via the hub endpoint →
    verify the new version is live + dispatchable."""
    plugin_id = "fft"

    # ---- 1. Pre-condition: install v1.1.0 -------------------------------
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)
    install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=120.0)
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)
    wait_for_plugin_announce(admin_client, plugin_id, timeout=30.0)

    # Capture the installed version pre-upgrade so we can assert the
    # transition is real. /upgrades endpoint conveniently reports it.
    upgrades_pre = admin_client.get(
        f"/admin/plugins/{plugin_id}/upgrades",
        params={"hub_url": mock_hub.base_url},
    )
    # Hub doesn't know about this plugin yet — endpoint should 404 from
    # the mock. We don't gate on this; just record current_version
    # from the actual install state.
    current_version = None
    if upgrades_pre.status_code == 200:
        current_version = upgrades_pre.json().get("current_version")

    # Derive the upgrade target version from the source version.
    # Manifest version is ``1.1.0`` (per plugins/magellon_fft_plugin/manifest.yaml);
    # bump patch.
    upgrade_version = "1.99.0"  # well above any real version so monotonicity passes

    # ---- 2. Build the upgrade archive + register with mock hub ---------
    upgrade_mpn = _repack_with_version(
        fft_mpn_archive, new_version=upgrade_version, out_dir=tmp_path,
    )
    upgrade_bytes = upgrade_mpn.read_bytes()
    upgrade_sha = hashlib.sha256(upgrade_bytes).hexdigest()
    archive_filename = f"fft-{upgrade_version}.mpn"

    mock_hub.set_archive(archive_filename, upgrade_bytes)
    mock_hub.set_plugin_json(
        plugin_id, _hub_plugin_json(
            plugin_id=plugin_id, version=upgrade_version,
            archive_filename=archive_filename, sha256=upgrade_sha,
        ),
    )

    # ---- 3. POST /upgrade-from-hub -------------------------------------
    resp = admin_client.post(
        f"/admin/plugins/{plugin_id}/upgrade-from-hub",
        json={"version": upgrade_version, "hub_url": mock_hub.base_url},
        timeout=180.0,
    )
    assert resp.status_code == 200, (
        f"upgrade-from-hub failed: {resp.status_code} {resp.text[:400]}"
    )
    upgrade_body = resp.json()
    assert upgrade_body["plugin_id"] == plugin_id
    assert upgrade_body["success"] is True

    # ---- 4. Verify the new version is live + announcing ----------------
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=60.0)
    wait_for_plugin_announce(admin_client, plugin_id, timeout=60.0)

    upgrades_post = admin_client.get(
        f"/admin/plugins/{plugin_id}/upgrades",
        params={"hub_url": mock_hub.base_url},
    )
    assert upgrades_post.status_code == 200, upgrades_post.text
    assert upgrades_post.json()["current_version"] == upgrade_version, (
        f"current_version did not transition. pre={current_version!r} "
        f"post={upgrades_post.json().get('current_version')!r}"
    )

    # ---- 5. Dispatch a task on the upgraded plugin ---------------------
    run_id = uuid.uuid4().hex[:8]
    host_dir = e2e_stack.gpfs_host_root / f"upgrade_e2e_{run_id}"
    host_dir.mkdir(parents=True, exist_ok=True)

    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed=99)
    arr = (rng.random((128, 128)) * 255).astype("uint8")
    img_path = host_dir / "post_upgrade.png"
    Image.fromarray(arr, mode="L").save(img_path)

    dispatch_path = str(img_path).replace("\\", "/")
    job_id = uuid.uuid4()
    dispatch_resp = admin_client.post(
        "/image/fft/batch_dispatch",
        json={
            "image_paths": [dispatch_path],
            "job_id": str(job_id),
            "name": f"upgrade_e2e {run_id}",
        },
        timeout=30.0,
    )
    assert dispatch_resp.status_code == 200, (
        f"post-upgrade dispatch failed: {dispatch_resp.status_code} "
        f"{dispatch_resp.text[:400]}"
    )

    # ---- 6. Cleanup ----------------------------------------------------
    uninstall_plugin(admin_client, plugin_id)


def test_upgrade_from_hub_rejects_sha_mismatch(
    e2e_stack, admin_client, mock_hub, fft_mpn_archive,
):
    """The threat model applies to upgrades too — refuse a tampered
    archive."""
    plugin_id = "fft"
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if not (pre.status_code == 200 and pre.json().get("installed")):
        install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=120.0)
        wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)

    # Real bytes, wrong sha — same shape as the install-from-hub sad path.
    archive_bytes = fft_mpn_archive.read_bytes()
    archive_name = fft_mpn_archive.name
    version = archive_name.removeprefix("fft-").removesuffix(".mpn")

    mock_hub.set_archive(archive_name, archive_bytes)
    mock_hub.set_plugin_json(
        plugin_id, _hub_plugin_json(
            plugin_id=plugin_id, version=version,
            archive_filename=archive_name, sha256="0" * 64,
        ),
    )

    resp = admin_client.post(
        f"/admin/plugins/{plugin_id}/upgrade-from-hub",
        json={
            "version": version, "hub_url": mock_hub.base_url,
            "force_downgrade": True,  # same version → force just in case
        },
    )
    assert resp.status_code == 502
    assert "sha256 mismatch" in resp.json()["detail"]

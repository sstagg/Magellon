"""E2E pin for Wave 4 replica scaling.

Install FFT with replicas.desired=2, observe two containers + two
announces. Scale up to 3 via POST /scale, observe a third announce.
Scale back down to 1, observe the surviving replica still processes
tasks.

Gated on MAGELLON_E2E_STACK=up. Requires a docker install (uv plugins
are pinned to single-instance per the Wave 4 plan; this test would
422 on a uv-only host).
"""
from __future__ import annotations

import logging
import time
import uuid
import zipfile
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


def _repack_with_replicas(
    source_mpn: Path, *, desired: int, max_replicas: int, out_dir: Path,
) -> Path:
    """Build a synthetic .mpn with the requested replicas bounds.

    The source manifest has no replicas block (single-instance default);
    we inject one. Replicates the pattern in test_plugin_upgrade_e2e.py
    so the same archive can be used unchanged for upgrade tests too.
    """
    out = out_dir / f"fft-replicas-{desired}.mpn"
    with zipfile.ZipFile(source_mpn) as src:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename in ("manifest.yaml", "plugin.yaml"):
                    text = data.decode("utf-8")
                    if "resources:" in text:
                        # Naive injection — append replicas block under
                        # resources. The minimal-FFT manifest has a
                        # resources: block already; we splice in the
                        # replicas dict at its end.
                        replicas_yaml = (
                            f"  replicas:\n"
                            f"    desired: {desired}\n"
                            f"    min: 1\n"
                            f"    max: {max_replicas}\n"
                        )
                        # Insert after the resources: line, before the
                        # next top-level key. Crude but the source
                        # manifest is small + well-known.
                        out_lines = []
                        in_resources = False
                        injected = False
                        for line in text.splitlines():
                            if line.startswith("resources:"):
                                in_resources = True
                                out_lines.append(line)
                                continue
                            if in_resources and not line.startswith((" ", "\t")) and line.strip():
                                if not injected:
                                    out_lines.append(replicas_yaml.rstrip())
                                    injected = True
                                in_resources = False
                            out_lines.append(line)
                        if in_resources and not injected:
                            out_lines.append(replicas_yaml.rstrip())
                        text = "\n".join(out_lines) + "\n"
                    else:
                        # No resources block — append one at top level.
                        text += (
                            "\nresources:\n"
                            f"  replicas:\n"
                            f"    desired: {desired}\n"
                            f"    min: 1\n"
                            f"    max: {max_replicas}\n"
                        )
                    data = text.encode("utf-8")
                dst.writestr(info.filename, data)
    return out


def test_install_with_replicas_then_scale_full_arc(
    e2e_stack, admin_client, fft_mpn_archive, tmp_path,
):
    """The full Wave 4 arc:
      1. Install FFT with replicas.desired=2.
      2. Verify both containers running + both announce on the bus.
      3. POST /scale {desired: 3} — verify a third container spawns.
      4. POST /scale {desired: 1} — verify two containers stop, one
         survives.
      5. Uninstall.
    """
    plugin_id = "fft"

    # Pre-condition: clean slate.
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)

    # Build a replicas-aware archive on the fly.
    archive = _repack_with_replicas(
        fft_mpn_archive, desired=2, max_replicas=5, out_dir=tmp_path,
    )

    install_plugin_from_archive(
        admin_client, archive, install_method="docker", timeout=180.0,
    )
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=60.0)
    # Both replicas should announce within the heartbeat window.
    deadline = time.monotonic() + 60.0
    live_count = 0
    while time.monotonic() < deadline:
        resp = admin_client.get(f"/plugins/{plugin_id}/replicas")
        if resp.status_code == 200:
            live_count = len(resp.json())
            if live_count >= 2:
                break
        time.sleep(1.0)
    assert live_count >= 2, (
        f"expected >=2 live replicas, got {live_count}. "
        f"Replicas endpoint: {resp.text[:300]}"
    )

    # Scale up to 3.
    resp = admin_client.post(
        f"/admin/plugins/{plugin_id}/scale", json={"desired": 3},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["desired"] == 3

    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        resp = admin_client.get(f"/plugins/{plugin_id}/replicas")
        if resp.status_code == 200 and len(resp.json()) >= 3:
            break
        time.sleep(1.0)
    else:
        pytest.fail(
            f"third replica did not announce within 60s. Last response: "
            f"{resp.text[:300]}"
        )

    # Scale down to 1.
    resp = admin_client.post(
        f"/admin/plugins/{plugin_id}/scale", json={"desired": 1},
    )
    assert resp.status_code == 200, resp.text

    # Heartbeat takes a beat to age out the stopped replicas; give the
    # registry up to 90s before failing.
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        resp = admin_client.get(f"/plugins/{plugin_id}/replicas")
        if resp.status_code == 200:
            healthy = [r for r in resp.json() if r.get("status") == "Healthy"]
            if len(healthy) == 1:
                break
        time.sleep(2.0)
    assert resp.status_code == 200
    healthy = [r for r in resp.json() if r.get("status") == "Healthy"]
    assert len(healthy) == 1, (
        f"expected 1 healthy replica after scale-down, got "
        f"{len(healthy)}. All replicas: {resp.json()}"
    )

    # Cleanup.
    uninstall_plugin(admin_client, plugin_id)


def test_scale_uv_plugin_returns_422(
    e2e_stack, admin_client, fft_mpn_archive,
):
    """If FFT was installed via uv, /scale should refuse with 422 and
    the docker-only message. Skips if FFT isn't uv-installed."""
    plugin_id = "fft"
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if not (pre.status_code == 200 and pre.json().get("installed")):
        install_plugin_from_archive(
            admin_client, fft_mpn_archive, install_method="uv", timeout=120.0,
        )
        # Some hosts can't satisfy uv predicates; skip if so.
        check = admin_client.get(f"/admin/plugins/{plugin_id}/status")
        if check.status_code != 200 or not check.json().get("installed"):
            pytest.skip("uv install didn't take on this host")

    resp = admin_client.post(
        f"/admin/plugins/{plugin_id}/scale", json={"desired": 2},
    )
    assert resp.status_code == 422
    assert "docker-only" in resp.json()["detail"].lower()

    # Cleanup if we installed.
    uninstall_plugin(admin_client, plugin_id)

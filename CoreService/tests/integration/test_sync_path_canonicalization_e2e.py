"""E2E pin for the Phase 0 sync-dispatcher path-canonicalization fix.

A Windows React client posting ``{"image_path": "C:/magellon/gpfs/..."}``
against a Docker plugin used to break silently — the plugin container
saw the host-absolute path and couldn't open it. Phase 0 added a
canonicalize-paths walker at the sync dispatch boundary so the wire
carries ``/gpfs/...`` regardless of the caller's OS.

This test exercises the fix on a live stack:

  1. The FFT plugin is up (installed via this test's fixture or
     pre-installed).
  2. CoreService has MAGELLON_GPFS_PATH set to a host-style root
     (typically ``C:/magellon/gpfs`` on a Windows-host deployment).
  3. We POST a sync run with a path under that host root.
  4. The plugin successfully reads the input and writes the output.
  5. The response's output_path is canonical ``/gpfs/...``.

Skip-clean cases:

  - MAGELLON_E2E_STACK != "up"  → handled by ``e2e_stack`` fixture.
  - MAGELLON_GPFS_PATH on the backend is already ``/gpfs`` (Linux
    deployment, walker is a no-op there)  → skip with an explanatory
    message; the Phase 0 unit tests cover the walker on Linux too.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import pytest

from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


def _backend_gpfs_path(admin_client) -> str:
    """Read MAGELLON_GPFS_PATH from CoreService's health/about surface,
    or fall back to the env var the test process sees. On the hybrid
    Windows-host deployment this is ``C:/magellon/gpfs`` (or similar);
    on Linux container deployments it's ``/gpfs``.

    The /dispatch/capabilities endpoint doesn't expose this, so we
    use an env-var fallback. If the backend disagrees with the env,
    the worst case is a confusing skip — the test won't false-pass.
    """
    import os
    return os.environ.get("MAGELLON_GPFS_PATH", "/gpfs")


def test_sync_dispatch_canonicalizes_host_path(
    e2e_stack,
    admin_client,
    fft_mpn_archive,
    tmp_path,
):
    """Phase 0 fix in action: post a host-absolute path, verify the
    plugin received and successfully opened it (which can only happen
    if the canonicalize walker rewrote it to /gpfs/... before httpx)."""
    plugin_id = "fft"

    gpfs_path = _backend_gpfs_path(admin_client)
    if gpfs_path == "/gpfs":
        pytest.skip(
            "MAGELLON_GPFS_PATH=/gpfs — canonicalize is a no-op on this "
            "deployment. Phase 0 unit tests cover the Linux case. Run "
            "this e2e on a Windows-host stack to exercise the rewrite."
        )

    # ---- 1. Ensure FFT is installed (idempotent) ------------------------
    status_resp = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if not (status_resp.status_code == 200 and status_resp.json().get("installed")):
        install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=120.0)
        wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)
        wait_for_plugin_announce(admin_client, plugin_id, timeout=30.0)

    # ---- 2. Confirm FFT advertises Capability.SYNC ----------------------
    caps_resp = admin_client.get("/dispatch/capabilities")
    assert caps_resp.status_code == 200, caps_resp.text
    fft_cap = next(
        (c for c in caps_resp.json()["categories"] if c["category"] == "fft"),
        None,
    )
    if not fft_cap or not fft_cap.get("supports_sync"):
        pytest.skip(
            "FFT plugin does not advertise SYNC capability on this stack — "
            f"got {fft_cap!r}. Test 2 needs a SYNC-capable FFT."
        )

    # ---- 3. Write a host-style input under the configured root ----------
    run_id = uuid.uuid4().hex[:8]
    host_dir = e2e_stack.gpfs_host_root / f"sync_canon_{run_id}"
    host_dir.mkdir(parents=True, exist_ok=True)

    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed=7)
    arr = (rng.random((128, 128)) * 255).astype("uint8")
    img_path = host_dir / "input.png"
    Image.fromarray(arr, mode="L").save(img_path)

    # Host-style path — the exact thing a Windows React client would
    # post. The walker MUST rewrite this to /gpfs/... before httpx.
    host_image_path = str(img_path).replace("\\", "/")
    assert host_image_path.lower().startswith(gpfs_path.replace("\\", "/").lower()), (
        f"test setup: {host_image_path!r} must be under {gpfs_path!r}"
    )

    # ---- 4. POST /dispatch/fft/run with the host path -------------------
    job_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())

    resp = admin_client.post(
        "/dispatch/fft/run",
        json={
            "image_id": image_id,
            "image_name": "input.png",
            "image_path": host_image_path,
            "engine_opts": {"height": 128},
        },
        timeout=60.0,
    )

    # If the walker fired, the plugin opens /gpfs/<rel>/input.png and
    # succeeds. If the walker DIDN'T fire, the plugin gets the literal
    # ``C:/magellon/gpfs/...`` string, can't open it, and returns 5xx.
    assert resp.status_code == 200, (
        f"sync dispatch failed — likely the canonicalize walker is "
        f"not in play. Status={resp.status_code} body={resp.text[:400]}"
    )

    # ---- 5. Verify the wire-shape response carries canonical paths ------
    body = resp.json()
    # The plugin's response includes output_path; on a hybrid host the
    # canonical /gpfs/... form should round-trip back.
    output_path = body.get("output_data", {}).get("output_path") or body.get("output_path")
    assert output_path, f"no output_path in response: {body}"
    assert output_path.startswith("/gpfs/") or output_path.startswith("\\gpfs\\"), (
        f"output_path is not canonical: {output_path!r}. The plugin saw "
        f"a host-style path, meaning the canonicalize walker didn't run."
    )

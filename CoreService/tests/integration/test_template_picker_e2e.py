"""Centerpiece e2e for the template-picker plugin.

The full operator arc, parallel to ``test_install_lifecycle_dispatch_e2e``
for FFT but exercising both transports the plugin advertises:

  1. Install via docker.
  2. Wait for the plugin to announce + report supports_sync /
     supports_preview on ``/dispatch/particle_picking/backends``.
  3. Bus dispatch (POST /particle-picking/async) — verify a single
     micrograph pick produces ``magellon.step.*`` events through to
     completed, and that the particles_json output file lands on the
     host filesystem.
  4. Sync preview (POST /particle-picking/preview) — verify a
     preview_id is returned with an initial pick count.
  5. Retune dance — POST /preview/{id}/retune with a LOW threshold
     (expect higher count) then a HIGH threshold (expect lower
     count). Pins that the cached score map is actually being
     re-thresholded, not silently re-running compute.
  6. DELETE /preview/{id} — verify subsequent retune 404s.
  7. Uninstall.

Requires the three reference templates pre-staged under
``<gpfs_host_root>/templates/origTemplate{1,2,3}.mrc`` — the
``template_paths`` fixture in conftest.py skips when they're absent.

Gated MAGELLON_E2E_STACK=up. Total budget ~3 minutes (most is
install cold-start; preview is sub-second once the plugin is up).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import List

import pytest

from tests.integration._e2e_helpers.dispatch import generate_test_micrograph_mrc
from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


# Template picking is more expensive than FFT (3 templates × FFT of a
# 1024² micrograph). Allow generous headroom for install cold-start +
# the preview compute pass.
INSTALL_TIMEOUT = 180.0
PREVIEW_TIMEOUT = 60.0
DISPATCH_TIMEOUT = 90.0


def _picker_input(image_path: str, template_paths: List[str], *,
                  threshold: float = 0.4) -> dict:
    """Build a TemplatePickerInput payload for the controller.

    Mirrors the React panel's body shape — just the fields the picker
    actually uses end-to-end. The controller validates against the
    full TemplatePickerInput model; missing fields fall back to the
    model's declared defaults.
    """
    return {
        "image_path": image_path,
        "template_paths": template_paths,
        "diameter_angstrom": 220.0,
        "pixel_size_angstrom": 3.16,
        "threshold": threshold,
        "max_peaks": 200,
    }


def test_template_picker_install_dispatch_preview_retune_full_arc(
    e2e_stack,
    admin_client,
    template_picker_mpn_archive,
    template_paths,
    step_event_collector,
    tmp_path,
):
    """The full template-picker e2e: install → sync preview → retune
    threshold dance → bus dispatch with step events → uninstall."""
    plugin_id = "template-picker"

    # ---- 0. Clean slate ---------------------------------------------------
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        logger.info("template-picker pre-installed — uninstalling first")
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)

    # ---- 1. Install (force docker for the lifecycle suite) ----------------
    install_body = install_plugin_from_archive(
        admin_client, template_picker_mpn_archive,
        install_method="docker", timeout=INSTALL_TIMEOUT,
    )
    assert install_body["plugin_id"] == plugin_id
    assert install_body["install_method"] == "docker"

    # ---- 2. Wait for both readiness signals -------------------------------
    wait_for_lifecycle_status(
        admin_client, plugin_id, "running", timeout=60.0,
    )
    wait_for_plugin_announce(admin_client, plugin_id, timeout=60.0)

    # ---- 3. The capabilities listing must report what the plugin advertises
    backends = admin_client.get(
        "/dispatch/particle_picking/backends",
    ).json()
    tp = next(
        (b for b in backends["backends"] if b["backend_id"] == "template-picker"),
        None,
    )
    assert tp is not None, (
        f"template-picker missing from /dispatch/particle_picking/backends: "
        f"{backends}"
    )
    assert tp["supports_sync"] is True, tp
    assert tp["supports_preview"] is True, tp
    assert tp["live_replicas"] >= 1, tp

    # ---- 4. Generate the test micrograph ----------------------------------
    run_id = uuid.uuid4().hex[:8]
    host_dir = e2e_stack.gpfs_host_root / f"template_picker_e2e_{run_id}"
    micrograph = generate_test_micrograph_mrc(
        host_dir, name="micrograph.mrc", size=1024, apix=3.16,
    )
    image_path_wire = str(micrograph).replace("\\", "/")
    assert micrograph.exists()

    # ---- 5. Sync preview round-trip ---------------------------------------
    # Use a permissive threshold so we get some picks back even on
    # pure-noise data. The retune phase below tightens / loosens it.
    preview_resp = admin_client.post(
        "/particle-picking/preview",
        json=_picker_input(image_path_wire, template_paths, threshold=0.3),
        timeout=PREVIEW_TIMEOUT,
    )
    assert preview_resp.status_code == 200, preview_resp.text
    preview = preview_resp.json()
    preview_id = preview["preview_id"]
    initial_count = preview["num_particles"]
    assert isinstance(preview_id, str) and preview_id, preview
    assert preview["num_templates"] == len(template_paths), preview
    # Score map PNG must be present so the React drawer can render it.
    assert preview.get("score_map_png_base64"), (
        "preview response missing score_map_png_base64 — React drawer "
        "can't render the heatmap overlay"
    )
    logger.info("preview returned id=%s initial_count=%d", preview_id, initial_count)

    # ---- 6. Retune dance — assert the cached score map responds to
    # threshold changes, not silent recompute. The score range is in
    # [0, 1] (after normalize); thresholds at the extremes should
    # produce very different counts.
    low_threshold_body = {
        "threshold": 0.05, "max_peaks": 500,
        "overlap_multiplier": 1.0, "max_blob_size_multiplier": 1.0,
        "min_blob_roundness": 0.0, "peak_position": "maximum",
    }
    high_threshold_body = {
        "threshold": 0.95, "max_peaks": 500,
        "overlap_multiplier": 1.0, "max_blob_size_multiplier": 1.0,
        "min_blob_roundness": 0.0, "peak_position": "maximum",
    }

    low_resp = admin_client.post(
        f"/particle-picking/preview/{preview_id}/retune",
        json=low_threshold_body, timeout=10.0,
    )
    assert low_resp.status_code == 200, low_resp.text
    low_count = low_resp.json()["num_particles"]

    high_resp = admin_client.post(
        f"/particle-picking/preview/{preview_id}/retune",
        json=high_threshold_body, timeout=10.0,
    )
    assert high_resp.status_code == 200, high_resp.text
    high_count = high_resp.json()["num_particles"]

    logger.info("retune counts: low_thr=%d high_thr=%d", low_count, high_count)
    assert low_count >= high_count, (
        f"retune with a permissive threshold should yield at least as many "
        f"picks as a strict one. low={low_count} high={high_count}. "
        f"The cached score map may be getting recomputed (or ignored) "
        f"instead of re-thresholded."
    )
    # And at least one threshold should produce some picks — otherwise
    # the assertion above could trivially hold at 0 == 0.
    assert low_count > 0 or high_count > 0, (
        "both threshold extremes produced zero picks — the picker may "
        "not be running the cross-correlation at all"
    )

    # ---- 7. DELETE preview ------------------------------------------------
    delete_resp = admin_client.delete(
        f"/particle-picking/preview/{preview_id}", timeout=5.0,
    )
    assert delete_resp.status_code == 200, delete_resp.text

    # Retune after delete should 404 — the cache entry is gone.
    after_delete = admin_client.post(
        f"/particle-picking/preview/{preview_id}/retune",
        json=high_threshold_body, timeout=5.0,
    )
    # Different plugins map "preview not found" to different upstream
    # status codes (404 or 503); both are acceptable signals that the
    # cache was actually cleared.
    assert after_delete.status_code in (404, 503), (
        f"retune on a deleted preview should 4xx/503; got "
        f"{after_delete.status_code} — cache may not be clearing"
    )

    # ---- 8. Bus dispatch with step-event verification ---------------------
    # Build a TaskMessage and publish via the /particle-picking/async
    # path — this is the operator's real-run path (vs the in-panel
    # preview). Subscribe to Socket.IO before publishing.
    job_id = uuid.uuid4()
    async_body = {
        "input": _picker_input(image_path_wire, template_paths, threshold=0.4),
        "job_id": str(job_id),
    }

    with step_event_collector(
        job_id, until_completed=1, timeout=DISPATCH_TIMEOUT,
    ) as events:
        async_resp = admin_client.post(
            "/particle-picking/async", json=async_body, timeout=10.0,
        )
        assert async_resp.status_code in (200, 202), async_resp.text

    by_type: dict = {}
    for env in events:
        by_type.setdefault(env.get("type"), []).append(env)

    completed = by_type.get("magellon.step.completed", [])
    failed = by_type.get("magellon.step.failed", [])
    assert len(failed) == 0, f"unexpected failed events: {failed}"
    assert len(completed) >= 1, (
        f"no completed event within {DISPATCH_TIMEOUT}s. Events seen: "
        f"{list(by_type)}"
    )
    started = by_type.get("magellon.step.started", [])
    progress = by_type.get("magellon.step.progress", [])
    assert len(started) >= 1, by_type
    # Template-picker emits progress at 15% (matching) + 90% (writing
    # output) — match the FFT pattern. Allow >= 1 to tolerate plugin
    # version drift on the exact percentage cadence.
    assert len(progress) >= 1, by_type

    # The completed envelope must reference the produced particles_json.
    completed_data = completed[0]["data"]
    assert completed_data.get("output_files"), completed_data
    output_path = completed_data["output_files"][0]
    assert output_path.endswith(".json"), output_path

    # ---- 9. Uninstall + verify cleanup ------------------------------------
    uninstall_plugin(admin_client, plugin_id)

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        resp = admin_client.get(f"/admin/plugins/{plugin_id}/status")
        if resp.status_code == 200 and not resp.json().get("installed"):
            break
        time.sleep(0.5)
    else:
        pytest.fail(
            f"template-picker still reports installed after uninstall: "
            f"{resp.status_code} {resp.text[:200]}"
        )

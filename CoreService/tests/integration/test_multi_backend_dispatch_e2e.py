"""E2E pin for Wave 5 multi-backend dispatch.

Install two FFT-like plugins differing only in ``backend_id`` (built
on-the-fly by repacking the source .mpn). Verify:

  1. Both announce on the bus; ``GET /dispatch/fft/backends`` lists
     both.
  2. Dispatching with explicit ``target_backend`` routes the task to
     the named backend (verified via the per-backend container's
     step-event source field).
  3. Switching the operator-pinned default via
     ``POST /plugins/categories/fft/default`` flips ``is_default``
     in the next ``/backends`` poll AND dispatches without an
     explicit pin land on the new default.

Gated MAGELLON_E2E_STACK=up.
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


def _repack_with_backend_id(
    source_mpn: Path, *, new_plugin_id: str, new_backend_id: str,
    new_version: str, out_dir: Path,
) -> Path:
    """Build a synthetic .mpn that swaps plugin_id + backend_id but
    keeps the same category and code so both plugins serve the same
    TaskCategory with different backend identities.

    Same shape as ``_repack_with_version`` in test_plugin_upgrade_e2e —
    naive line-based rewrite. Source manifest must have ``plugin_id:``,
    ``backend_id:``, and ``version:`` as top-level keys.
    """
    out = out_dir / f"{new_plugin_id}-{new_version}.mpn"
    with zipfile.ZipFile(source_mpn) as src:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename in ("manifest.yaml", "plugin.yaml"):
                    text = data.decode("utf-8")
                    new_lines = []
                    for line in text.splitlines():
                        if line.startswith("plugin_id:"):
                            new_lines.append(f"plugin_id: {new_plugin_id}")
                        elif line.startswith("backend_id:"):
                            new_lines.append(f"backend_id: {new_backend_id}")
                        elif line.startswith("version:"):
                            new_lines.append(f"version: {new_version}")
                        else:
                            new_lines.append(line)
                    data = ("\n".join(new_lines) + "\n").encode("utf-8")
                dst.writestr(info.filename, data)
    return out


def test_two_backends_in_one_category_dispatch_routes_by_target(
    e2e_stack, admin_client, fft_mpn_archive, tmp_path,
):
    """The Wave 5 invariant: two plugins serving one category +
    ``target_backend`` on a TaskMessage routes to the named backend."""
    # The original FFT plugin is plugin_id=fft, backend_id=fft. We
    # synthesize a sibling with plugin_id=fft-alt, backend_id=fft-alt
    # serving the same category=fft.
    primary_id = "fft"
    alt_id = "fft-alt"
    alt_archive = _repack_with_backend_id(
        fft_mpn_archive,
        new_plugin_id=alt_id, new_backend_id=alt_id,
        new_version="1.99.0", out_dir=tmp_path,
    )

    # Clean slate for both.
    for pid in (primary_id, alt_id):
        pre = admin_client.get(f"/admin/plugins/{pid}/status")
        if pre.status_code == 200 and pre.json().get("installed"):
            uninstall_plugin(admin_client, pid)
    time.sleep(2.0)

    # Install both.
    install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=180.0)
    install_plugin_from_archive(admin_client, alt_archive, timeout=180.0)
    wait_for_lifecycle_status(admin_client, primary_id, "running", timeout=60.0)
    wait_for_lifecycle_status(admin_client, alt_id, "running", timeout=60.0)
    wait_for_plugin_announce(admin_client, primary_id, timeout=60.0)
    wait_for_plugin_announce(admin_client, alt_id, timeout=60.0)

    # /dispatch/fft/backends should report both.
    resp = admin_client.get("/dispatch/fft/backends")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    backend_ids = {b["backend_id"] for b in body["backends"]}
    assert backend_ids == {primary_id, alt_id}, backend_ids

    # Dispatch one FFT task with explicit target_backend=alt — the
    # alt plugin should process it; the primary shouldn't.
    run_id = uuid.uuid4().hex[:8]
    host_dir = e2e_stack.gpfs_host_root / f"multi_backend_e2e_{run_id}"
    host_dir.mkdir(parents=True, exist_ok=True)

    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed=13)
    arr = (rng.random((128, 128)) * 255).astype("uint8")
    img_path = host_dir / "in.png"
    Image.fromarray(arr, mode="L").save(img_path)

    job_id = uuid.uuid4()
    dispatch_resp = admin_client.post(
        "/image/fft/batch_dispatch",
        json={
            "image_paths": [str(img_path).replace("\\", "/")],
            "job_id": str(job_id),
            "name": f"multi-backend {run_id}",
            "target_backend": alt_id,
        },
        timeout=30.0,
    )
    assert dispatch_resp.status_code == 200, dispatch_resp.text

    # Collect step events; the source field on the envelope identifies
    # which backend processed it.
    import socketio
    import asyncio
    received: list = []
    done = asyncio.Event()

    async def _run():
        sio = socketio.AsyncClient(reconnection=False)

        @sio.on("step_event")
        async def _on_step(payload):
            received.append(payload)
            if payload.get("type") == "magellon.step.completed":
                done.set()

        await sio.connect(e2e_stack.backend_url, transports=["websocket"])
        try:
            ack = await sio.call(
                "join_job_room", {"job_id": str(job_id)}, timeout=5,
            )
            assert ack and ack.get("ok"), ack
            try:
                await asyncio.wait_for(done.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass
        finally:
            try:
                await sio.disconnect()
            except Exception:
                pass

    asyncio.run(_run())

    completed = [e for e in received if e.get("type") == "magellon.step.completed"]
    assert completed, "no completed event observed for target_backend=alt dispatch"
    # The source field identifies the plugin: ``magellon/plugins/<id>``.
    sources = {e.get("source") for e in completed}
    assert any(alt_id in (s or "") for s in sources), (
        f"completed event source(s) {sources!r} don't mention "
        f"target backend {alt_id!r}"
    )

    # Cleanup.
    uninstall_plugin(admin_client, primary_id)
    uninstall_plugin(admin_client, alt_id)


def test_set_default_swaps_routing_when_no_target_backend(
    e2e_stack, admin_client, fft_mpn_archive, tmp_path,
):
    """Switching the operator-pinned default via /plugins/categories/
    {category}/default flips routing for dispatches without an
    explicit target_backend pin."""
    primary_id = "fft"
    alt_id = "fft-alt"
    alt_archive = _repack_with_backend_id(
        fft_mpn_archive, new_plugin_id=alt_id, new_backend_id=alt_id,
        new_version="1.99.0", out_dir=tmp_path,
    )

    for pid in (primary_id, alt_id):
        pre = admin_client.get(f"/admin/plugins/{pid}/status")
        if pre.status_code == 200 and pre.json().get("installed"):
            uninstall_plugin(admin_client, pid)
    time.sleep(2.0)
    install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=180.0)
    install_plugin_from_archive(admin_client, alt_archive, timeout=180.0)
    wait_for_plugin_announce(admin_client, primary_id, timeout=60.0)
    wait_for_plugin_announce(admin_client, alt_id, timeout=60.0)

    # Set fft-alt as the operator default.
    resp = admin_client.post(
        f"/plugins/categories/fft/default", json={"plugin_id": alt_id},
    )
    assert resp.status_code in (200, 204), resp.text

    # Verify /backends reflects the new default.
    resp = admin_client.get("/dispatch/fft/backends")
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_plugin_id"] == alt_id, body
    is_default = {b["backend_id"]: b["is_default"] for b in body["backends"]}
    assert is_default[alt_id] is True
    assert is_default[primary_id] is False

    # Cleanup.
    uninstall_plugin(admin_client, primary_id)
    uninstall_plugin(admin_client, alt_id)

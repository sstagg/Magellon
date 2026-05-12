"""E2E pin for Wave 4 restart_policy.

The Phase 13 unit tests prove ``--restart`` lands on the docker run
command and the systemd template parameterizes ``Restart=``. This
test proves the policy ACTUALLY restarts the container after a crash.

  1. Install FFT (docker, on-failure policy by default).
  2. Verify the container is running.
  3. ``docker kill`` it to simulate a crash.
  4. Within 30s, ``docker inspect`` should report the container
     running again (docker's restart-on-failure semantics).

Gated on MAGELLON_E2E_STACK=up.
"""
from __future__ import annotations

import logging
import subprocess
import time

import pytest

from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


def _container_name_for(plugin_id: str, plugins_dir_hint: str | None = None) -> str:
    """Compose the container name DockerInstaller assigns to the
    single-replica case (no -<i> suffix)."""
    return f"magellon-plugin-{plugin_id}"


def _docker_inspect_status(container_name: str) -> str:
    """Return the container's State.Status via ``docker inspect``, or
    empty string on failure."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip().lower()


def test_docker_restart_on_failure_actually_restarts(
    e2e_stack, admin_client, fft_mpn_archive,
):
    """Manifest-default restart_policy=on-failure → after docker kill,
    the container restarts within docker's automatic backoff window."""
    plugin_id = "fft"

    # Clean slate.
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)

    install_plugin_from_archive(
        admin_client, fft_mpn_archive, install_method="docker", timeout=180.0,
    )
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=60.0)
    wait_for_plugin_announce(admin_client, plugin_id, timeout=60.0)

    container_name = _container_name_for(plugin_id)
    assert _docker_inspect_status(container_name) == "running", (
        f"container {container_name!r} did not reach running state"
    )

    # Send the equivalent of "the process inside crashed" — docker kill
    # delivers SIGKILL to PID 1 inside the container. Combined with the
    # ``--restart=on-failure:5`` flag the installer set, docker should
    # restart it within seconds.
    result = subprocess.run(
        ["docker", "kill", "--signal=SIGKILL", container_name],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"docker kill failed: {result.stderr or result.stdout}"
    )

    # Poll for the container to come back up. The State.Status transitions
    # through ``exited`` (briefly) then back to ``running`` once docker's
    # restart manager retriggers.
    deadline = time.monotonic() + 30.0
    final_state = ""
    while time.monotonic() < deadline:
        final_state = _docker_inspect_status(container_name)
        if final_state == "running":
            break
        time.sleep(1.0)
    assert final_state == "running", (
        f"container did not restart within 30s; final state was "
        f"{final_state!r}. docker's restart manager may have given up "
        f"(check ``docker inspect`` RestartCount)."
    )

    # Sanity: the bus should re-announce the plugin once it's back up.
    wait_for_plugin_announce(admin_client, plugin_id, timeout=60.0)

    # Cleanup.
    uninstall_plugin(admin_client, plugin_id)

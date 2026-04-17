"""Docker-backed plugin runner (H2).

Spawns a plugin Docker image with operator-supplied env vars, volume
mounts, and network, then tracks the container ID so CoreService can
stop / remove it later. Shells out to the ``docker`` CLI — avoids
adding the Python docker SDK as a dependency and makes failures easier
to debug (just re-run the printed command).

Scope notes:

- **Lifecycle only.** This module does NOT generate plugin config,
  inject RMQ credentials, or validate that the image actually contains
  a Magellon plugin. If the operator installs an image whose config
  points at the wrong RMQ, the container runs but never announces —
  CoreService shows "installed but not announcing" state and the
  operator fixes their config. Smart config injection is a follow-up
  item (see docs/UNIFIED_PLATFORM_PLAN.md H2 follow-ups).

- **No persistence.** The in-memory registry survives only for the
  lifetime of the CoreService process. A restart loses the ``install_id``
  ↔ ``container_id`` mapping; operators need to reinstall. Matches the
  plan's "no central registry yet" for H2.

- **Security.** POST /plugins/install accepts an arbitrary image ref
  and runs it with Docker privileges — it's effectively code execution
  on the host. Gate behind an authenticated admin role before exposing
  beyond localhost.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class VolumeMount:
    """One host→container bind mount. Read-only flag is optional; most
    plugin mounts (``/gpfs`` for data, ``/jobs`` for output) are RW."""
    host_path: str
    container_path: str
    read_only: bool = False

    def to_docker_flag(self) -> str:
        flag = f"{self.host_path}:{self.container_path}"
        if self.read_only:
            flag += ":ro"
        return flag


@dataclass
class InstalledPlugin:
    """One row in the installed-plugins registry.

    ``install_id`` is CoreService-owned (short UUID). ``container_id``
    is the Docker-reported long id — used when shelling back out to
    ``docker stop`` / ``docker rm``. ``state`` reflects what
    CoreService last observed; it's best-effort because we don't
    subscribe to Docker events — a container killed by ``docker kill``
    from outside CoreService shows ``running`` until the next refresh.
    """
    install_id: str
    image_ref: str
    container_id: str
    container_name: str
    state: str = "running"
    env: Dict[str, str] = field(default_factory=dict)
    volumes: List[VolumeMount] = field(default_factory=list)
    network: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "install_id": self.install_id,
            "image_ref": self.image_ref,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "state": self.state,
            "env": dict(self.env),
            "volumes": [v.__dict__ for v in self.volumes],
            "network": self.network,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class DockerNotAvailable(RuntimeError):
    """Raised when the ``docker`` CLI isn't reachable. Lets the endpoint
    return a 503 with a clear message instead of leaking subprocess
    internals to the client."""


class DockerPluginRunner:
    """Thread-safe spawn/stop/remove wrapper around ``docker`` CLI."""

    def __init__(self, *, docker_binary: str = "docker") -> None:
        self._docker = docker_binary
        self._lock = threading.Lock()

    def _run_docker(self, args: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
        """Single chokepoint for docker invocations — one place to log
        commands, one place to translate FileNotFoundError into our
        typed DockerNotAvailable.
        """
        cmd = [self._docker, *args]
        logger.info("docker exec: %s", " ".join(shlex.quote(a) for a in cmd))
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise DockerNotAvailable(
                "The 'docker' CLI is not on PATH. Install Docker or "
                "run CoreService in an environment with docker mounted."
            ) from exc

    def ping(self) -> bool:
        """Lightweight probe — ``docker version`` returns non-zero when
        the daemon is unreachable. Used by the /plugins/installed
        endpoint to refuse early with a clean error."""
        try:
            result = self._run_docker(["version", "--format", "{{.Server.Version}}"], check=False)
        except DockerNotAvailable:
            return False
        return result.returncode == 0

    def run_image(
        self,
        *,
        image_ref: str,
        env: Optional[Dict[str, str]] = None,
        volumes: Optional[List[VolumeMount]] = None,
        network: Optional[str] = None,
        name_prefix: str = "magellon-plugin",
    ) -> InstalledPlugin:
        """Start an image in detached mode; return the tracking record.

        Uses ``--restart unless-stopped`` so a plugin crash loops back
        up without operator intervention — matches how the fixed-set
        plugins run today under docker-compose. If an operator wants a
        one-shot install they can ``docker rm`` afterwards.
        """
        env = env or {}
        volumes = volumes or []

        install_id = uuid4().hex[:12]
        container_name = f"{name_prefix}-{install_id}"

        args: List[str] = ["run", "--detach", "--name", container_name, "--restart", "unless-stopped"]
        for key, value in env.items():
            args.extend(["-e", f"{key}={value}"])
        for v in volumes:
            args.extend(["-v", v.to_docker_flag()])
        if network:
            args.extend(["--network", network])
        args.append(image_ref)

        with self._lock:
            try:
                result = self._run_docker(args)
            except subprocess.CalledProcessError as exc:
                # docker run prints the error on stderr — include it
                # verbatim so the UI / operator sees the real cause.
                stderr = (exc.stderr or "").strip() or str(exc)
                logger.warning("docker run failed for %s: %s", image_ref, stderr)
                return InstalledPlugin(
                    install_id=install_id,
                    image_ref=image_ref,
                    container_id="",
                    container_name=container_name,
                    state="failed",
                    env=env,
                    volumes=volumes,
                    network=network,
                    error=stderr,
                )

        container_id = (result.stdout or "").strip()
        return InstalledPlugin(
            install_id=install_id,
            image_ref=image_ref,
            container_id=container_id,
            container_name=container_name,
            state="running",
            env=env,
            volumes=volumes,
            network=network,
        )

    def stop(self, entry: InstalledPlugin, *, timeout_seconds: int = 10) -> None:
        """Stop the container; updates ``entry.state`` in place.

        Uses ``docker stop -t <timeout>`` so the plugin gets a chance
        to drain in-flight work before SIGKILL.
        """
        if not entry.container_id:
            return
        try:
            self._run_docker(
                ["stop", "-t", str(timeout_seconds), entry.container_id],
                check=False,
            )
            entry.state = "stopped"
        except DockerNotAvailable:
            raise
        except Exception as exc:  # noqa: BLE001 — keep registry consistent on transient failures
            entry.error = str(exc)

    def remove(self, entry: InstalledPlugin) -> None:
        """``docker rm -f`` — stops + removes in one shot.

        Used by the /installed DELETE endpoint. Idempotent: if the
        container is already gone, the CLI exits non-zero and we
        swallow it (caller still wants the registry entry dropped).
        """
        if not entry.container_id:
            return
        try:
            self._run_docker(["rm", "-f", entry.container_id], check=False)
        except DockerNotAvailable:
            raise
        entry.state = "removed"

    def inspect_state(self, entry: InstalledPlugin) -> Optional[str]:
        """Refresh the container state from Docker.

        Returns the Docker state string ("running", "exited", "dead",
        etc.) or None if the container is no longer known to Docker
        (e.g. removed out-of-band). Not called on every /installed read
        — would be O(N) docker calls per listing. Callers refresh
        on-demand.
        """
        if not entry.container_id:
            return None
        result = self._run_docker(
            ["inspect", "--format", "{{.State.Status}}", entry.container_id],
            check=False,
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip() or None


_RUNNER: Optional[DockerPluginRunner] = None


def get_runner() -> DockerPluginRunner:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = DockerPluginRunner()
    return _RUNNER


__all__ = [
    "DockerNotAvailable",
    "DockerPluginRunner",
    "InstalledPlugin",
    "VolumeMount",
    "get_runner",
]

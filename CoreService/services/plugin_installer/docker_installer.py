"""``DockerInstaller`` — installs plugins via Docker (P5).

Two sub-modes per the manifest's install entry:

  - ``image: ghcr.io/.../foo:1.2.3`` — ``docker pull`` then run
    (fastest install, no build step)
  - ``dockerfile: Dockerfile`` — ``docker build`` from the unpacked
    archive directory, then run

Per-plugin layout under ``<plugins_dir>/<plugin_id>/``:

    <plugin_id>/
    ├── manifest.yaml          (extracted from .mpn for diagnostics)
    ├── plugin.yaml            (legacy alias)
    ├── Dockerfile             (only present when build mode is used)
    ├── install_state.json     (image_ref, image_was_built, container_name)
    └── ...                    (rest of archive — useful for ops debug)

Container name: ``magellon-plugin-<plugin_id>``. Stable so
``docker ps --filter name=magellon-plugin-<id>`` always finds it,
and uninstall doesn't need to remember a random suffix.

Image lifecycle on uninstall:

  - Built images (``image_was_built=true``) are removed via
    ``docker rmi`` — they're per-plugin, no one else uses them
  - Pulled images are kept — they may be cached for re-install or
    shared across deployments

Subprocess runner is injectable so unit tests don't shell out to
docker. Real-docker integration tests live elsewhere and skip when
the daemon isn't reachable.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

from magellon_sdk.archive.manifest import InstallSpec, PluginArchiveManifest

from services.plugin_installer.port_allocator import PluginPortAllocator
from services.plugin_installer.predicates import HostInfo, evaluate_predicates
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)

logger = logging.getLogger(__name__)


SubprocessRunner = Callable[..., subprocess.CompletedProcess]
STATE_FILENAME = "install_state.json"


def _default_subprocess_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    if kwargs.get("text") and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs.setdefault("errors", "replace")
    return subprocess.run(*args, **kwargs)


def _replace_existing(path: Path) -> None:
    """Remove a path (file or dir) if it exists. Used before
    renaming a .bak target so we don't accumulate stale backups
    across upgrade cycles."""
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


class DockerInstaller:
    """Installer impl for the ``docker`` install method."""

    method = "docker"

    def __init__(
        self,
        plugins_dir: Path,
        *,
        docker_command: str = "docker",
        network: Optional[str] = None,
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
        port_allocator: Optional[PluginPortAllocator] = None,
        container_port: int = 8000,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.docker_command = docker_command
        self.network = network
        self._run = subprocess_runner
        # R2 #4: same allocator the UvInstaller uses (shared
        # plugins_dir → shared assignment file → no port collisions
        # across install methods on the same host).
        self._port_allocator = port_allocator or PluginPortAllocator(self.plugins_dir)
        # FastAPI plugins listen on port 8000 inside the container by
        # convention; published to the allocated host port via -p.
        self.container_port = container_port

    # ------------------------------------------------------------------
    # Installer Protocol
    # ------------------------------------------------------------------

    def supports(self, install_spec: InstallSpec, host: HostInfo) -> List[str]:
        if install_spec.method != "docker":
            return [f"method != docker (got {install_spec.method!r})"]
        if not install_spec.image and not install_spec.dockerfile:
            return ["docker install spec missing both 'image' and 'dockerfile'"]
        return evaluate_predicates(install_spec.requires, host)

    def install(
        self,
        archive_path: Path,
        manifest: PluginArchiveManifest,
        install_spec: InstallSpec,
        runtime: RuntimeConfig,
    ) -> InstallResult:
        plugin_id = manifest.plugin_id
        target = self.plugins_dir / plugin_id

        if target.exists():
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method=self.method,
                error=f"plugin {plugin_id} already installed at {target}",
            )

        target.mkdir(parents=True)
        logs: list[str] = []
        image_ref: Optional[str] = None
        image_was_built = False
        started_replicas: list[dict] = []

        # Replica count — manifest declares desired/min/max; we honor
        # ``desired`` at install time, capped to ``max``. Operators
        # rescale later via POST /admin/plugins/{id}/scale.
        replica_count = 1
        if manifest.resources.replicas is not None:
            replica_count = max(1, min(
                manifest.resources.replicas.desired,
                manifest.resources.replicas.max,
            ))

        try:
            # 1. Extract archive (we keep the source on disk for ops debug
            # AND for build mode — docker build needs the Dockerfile.)
            self._extract_archive(archive_path, target)
            logs.append(f"extracted {archive_path} -> {target}")

            # 2. Decide pull vs build. Prefer pre-built `image:` when set
            # (no build step = much faster install).
            if install_spec.image:
                image_ref = install_spec.image
                self._docker_pull(image_ref, logs)
            elif install_spec.dockerfile:
                image_ref = self._built_image_tag(manifest)
                self._docker_build(
                    target, install_spec.dockerfile, install_spec.build_context or ".",
                    image_ref, logs,
                )
                image_was_built = True
            else:
                # supports() should have caught this, but defense in depth.
                raise RuntimeError("docker install spec has neither image nor dockerfile")

            # 3. Spawn N replicas. Single-replica installs match the
            # legacy v1.0 shape (container name = "magellon-plugin-<id>",
            # no -0 suffix); multi-replica installs append -<i> per
            # replica so docker container names stay unique.
            for replica_id in range(replica_count):
                container_name = self._container_name(plugin_id, replica_id, replica_count)
                port_key = self._port_key(plugin_id, replica_id)
                host_port = self._port_allocator.allocate(port_key)
                http_endpoint = f"http://127.0.0.1:{host_port}"
                logs.append(
                    f"replica {replica_id}: allocated host port {host_port} "
                    f"→ {http_endpoint}; container {container_name}",
                )
                self._docker_run(
                    container_name, image_ref, runtime, logs,
                    host_port=host_port, http_endpoint=http_endpoint,
                    restart_policy=manifest.lifecycle.restart_policy,
                    restart_max_retries=manifest.lifecycle.restart_max_retries,
                )
                started_replicas.append({
                    "replica_id": replica_id,
                    "container_name": container_name,
                    "host_port": host_port,
                })

            # 4. Write state for uninstall + scale to find later.
            #    v1.1 state shape: top-level ``container_name`` mirrors
            #    the first replica (legacy callers); ``replicas`` is the
            #    canonical list.
            self._write_state(target, {
                "plugin_id": plugin_id,
                "version": manifest.version,
                "method": "docker",
                "image_ref": image_ref,
                "image_was_built": image_was_built,
                "container_name": started_replicas[0]["container_name"],
                "replicas": started_replicas,
                # Persist the restart policy so ``scale_to`` can spawn
                # additional replicas with the same flag (we don't have
                # the original manifest at scale time).
                "restart_policy": manifest.lifecycle.restart_policy,
                "restart_max_retries": manifest.lifecycle.restart_max_retries,
            })

            return InstallResult(
                success=True,
                plugin_id=plugin_id,
                install_method=self.method,
                install_dir=target,
                http_endpoint=f"http://127.0.0.1:{started_replicas[0]['host_port']}",
                port=started_replicas[0]["host_port"],
                logs="\n".join(logs),
            )

        except Exception as exc:  # noqa: BLE001
            # Roll back in reverse order — each step is best-effort
            # because a failure at step N might mean step N-1 didn't
            # actually finish either.
            for replica in started_replicas:
                self._docker_stop_rm(replica["container_name"], swallow=True)
                self._port_allocator.release(
                    self._port_key(plugin_id, replica["replica_id"]),
                )
            if image_was_built and image_ref:
                self._docker_rmi(image_ref, swallow=True)
            shutil.rmtree(target, ignore_errors=True)
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method=self.method,
                error=str(exc),
                logs="\n".join(logs),
            )

    def uninstall(
        self, plugin_id: str, *, preserve_as_backup: bool = False,
    ) -> UninstallResult:
        target = self.plugins_dir / plugin_id
        if not target.is_dir():
            return UninstallResult(
                success=False,
                plugin_id=plugin_id,
                error=f"plugin {plugin_id} not installed under {self.plugins_dir}",
            )

        try:
            state = self._read_state(target)
        except FileNotFoundError:
            # Half-uninstalled previously. Best effort: remove the
            # directory and report what we couldn't clean up. Backup
            # mode can't preserve a state-less install — the rollback
            # would have nothing to read.
            shutil.rmtree(target, ignore_errors=True)
            return UninstallResult(
                success=False,
                plugin_id=plugin_id,
                error=f"install_state.json missing — directory removed but "
                      f"docker container/image cleanup may be incomplete",
            )

        # 1. Stop + remove every container in the replica set. v1.1
        # state has a ``replicas`` list; v1.0 had a single
        # ``container_name`` we synthesize a one-entry list from.
        replicas = state.get("replicas")
        if not isinstance(replicas, list) or not replicas:
            legacy_name = state.get("container_name")
            if legacy_name:
                replicas = [{"container_name": legacy_name, "replica_id": 0}]
            else:
                replicas = []
        for replica in replicas:
            name = replica.get("container_name")
            if not name:
                continue
            try:
                self._docker_stop_rm(name, swallow=False)
            except Exception as exc:  # noqa: BLE001
                return UninstallResult(
                    success=False, plugin_id=plugin_id,
                    error=f"docker stop/rm failed for {name!r}: {exc}",
                )
            # Release the port assignment so a future install gets the
            # same slot. Best-effort; missing key is a no-op.
            try:
                self._port_allocator.release(
                    self._port_key(plugin_id, replica.get("replica_id", 0)),
                )
            except Exception:  # noqa: BLE001
                pass

        # 2. Backup mode: preserve image (rollback re-runs the same
        # one) and rename the dir. Don't rmi anything.
        if preserve_as_backup:
            try:
                version = state.get("version", "unknown")
                backup = self.plugins_dir / f"{plugin_id}.{version}.bak"
                _replace_existing(backup)
                target.rename(backup)
                return UninstallResult(success=True, plugin_id=plugin_id)
            except Exception as exc:  # noqa: BLE001
                return UninstallResult(
                    success=False, plugin_id=plugin_id,
                    error=f"backup rename failed: {exc}",
                )

        # 3. Regular uninstall: remove built images; preserve pulled
        # ones (may be shared).
        if state.get("image_was_built") and state.get("image_ref"):
            try:
                self._docker_rmi(state["image_ref"], swallow=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "docker rmi failed for %s: %s — continuing",
                    state["image_ref"], exc,
                )

        # 4. Remove the install dir last so a docker failure leaves
        # the state file for diagnostics.
        try:
            shutil.rmtree(target)
        except Exception as exc:  # noqa: BLE001
            return UninstallResult(
                success=False,
                plugin_id=plugin_id,
                error=f"directory removal failed: {exc}",
            )

        # Release the port — a future install of any plugin can
        # reuse it.
        self._port_allocator.release(plugin_id)
        return UninstallResult(success=True, plugin_id=plugin_id)

    def is_installed(self, plugin_id: str) -> bool:
        target = self.plugins_dir / plugin_id
        # Require both the directory AND the state marker so a
        # half-uninstalled or hand-created directory isn't reported
        # as installed.
        return target.is_dir() and (target / STATE_FILENAME).is_file()

    # ------------------------------------------------------------------
    # Subprocess wrappers
    # ------------------------------------------------------------------

    def _docker_pull(self, image_ref: str, logs: list[str]) -> None:
        cmd = [self.docker_command, "pull", image_ref]
        logs.append(f"+ {' '.join(cmd)}")
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker pull failed: {result.stderr or result.stdout}"
            )
        logs.append((result.stdout or "").rstrip())

    def _docker_build(
        self,
        target: Path,
        dockerfile_rel: str,
        build_context_rel: str,
        image_tag: str,
        logs: list[str],
    ) -> None:
        dockerfile = target / dockerfile_rel
        build_context = target / build_context_rel
        cmd = [
            self.docker_command, "build",
            "-t", image_tag,
            "-f", str(dockerfile),
            str(build_context),
        ]
        logs.append(f"+ {' '.join(cmd)}")
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker build failed: {result.stderr or result.stdout}"
            )
        logs.append((result.stdout or "").rstrip())

    def _docker_run(
        self,
        container_name: str,
        image_ref: str,
        runtime: RuntimeConfig,
        logs: list[str],
        *,
        host_port: Optional[int] = None,
        http_endpoint: Optional[str] = None,
        restart_policy: str = "on-failure",
        restart_max_retries: int = 5,
    ) -> None:
        cmd = [
            self.docker_command, "run",
            "-d",  # detached
            "--name", container_name,
        ]
        # Restart policy (Wave 4 / manifest v1.1) — maps the manifest
        # vocabulary directly to docker's --restart flag. ``on-failure``
        # carries a max-retries count; the others are bare.
        flag = self._restart_flag(restart_policy, restart_max_retries)
        if flag is not None:
            cmd.extend(["--restart", flag])
        if self.network:
            cmd.extend(["--network", self.network])
        # R2 #4: publish the host's allocated port → container's
        # FastAPI port. CoreService reaches the plugin at
        # ``http://127.0.0.1:<host_port>``; the container itself
        # binds the conventional 8000.
        if host_port is not None:
            cmd.extend(["-p", f"{host_port}:{self.container_port}"])
        container_gpfs_root = self._container_gpfs_root(runtime.gpfs_root)
        # Mount the host GPFS root at the plugin's canonical data-plane
        # path. Linux hosts are usually symmetric (/gpfs:/gpfs);
        # Windows hosts mount C:/... at /gpfs inside the container.
        cmd.extend(["-v", f"{runtime.gpfs_root}:{container_gpfs_root}"])
        # Deployment-supplied env vars.
        cmd.extend(["-e", f"MAGELLON_BROKER_URL={runtime.broker_url}"])
        cmd.extend(["-e", f"MAGELLON_GPFS_PATH={container_gpfs_root}"])
        cmd.extend(["-e", f"HOST_GPFS_PATH={runtime.gpfs_root}"])
        cmd.extend(["-e", f"MAGELLON_HOME_DIR={container_gpfs_root}"])
        if http_endpoint:
            cmd.extend(["-e", f"MAGELLON_PLUGIN_HTTP_ENDPOINT={http_endpoint}"])
            cmd.extend(["-e", "MAGELLON_PLUGIN_HOST=0.0.0.0"])
            cmd.extend(["-e", f"MAGELLON_PLUGIN_PORT={self.container_port}"])
        for k, v in sorted(runtime.extra_env.items()):
            cmd.extend(["-e", f"{k}={v}"])
        cmd.append(image_ref)

        logs.append(f"+ {' '.join(cmd)}")
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"docker run failed: {result.stderr or result.stdout}"
            )
        logs.append((result.stdout or "").rstrip())

    def scale_to(
        self, plugin_id: str, *, desired: int, runtime: RuntimeConfig,
    ) -> tuple[int, int]:
        """Add or remove replicas to reach ``desired`` count.

        Returns ``(current_count, new_count)``. Raises ``ValueError``
        when the request violates the manifest's min/max bounds or the
        plugin isn't installed under docker.

        Scale-up reuses the recorded image_ref + restart policy from
        install_state.json — no archive re-extraction. Scale-down
        stops+removes the highest-numbered replicas first to keep
        replica_id assignments dense.
        """
        target = self.plugins_dir / plugin_id
        if not target.is_dir():
            raise ValueError(f"plugin {plugin_id!r} not installed")
        try:
            state = self._read_state(target)
        except FileNotFoundError as exc:
            raise ValueError(
                f"install_state.json missing for {plugin_id!r}; "
                f"scale needs a clean install"
            ) from exc

        # Read manifest from the install dir to get min/max bounds.
        manifest_path = target / "manifest.yaml"
        if not manifest_path.is_file():
            manifest_path = target / "plugin.yaml"
        if not manifest_path.is_file():
            raise ValueError(
                f"manifest.yaml missing from {target} — re-install the plugin"
            )
        from magellon_sdk.archive.manifest import load_manifest_bytes
        manifest = load_manifest_bytes(manifest_path.read_bytes())
        rp = manifest.resources.replicas
        rp_min = rp.min if rp else 1
        rp_max = rp.max if rp else 1
        if not (rp_min <= desired <= rp_max):
            raise ValueError(
                f"desired={desired} outside manifest bounds "
                f"[min={rp_min}, max={rp_max}]"
            )

        replicas: list[dict] = list(state.get("replicas") or [])
        if not replicas:
            legacy_name = state.get("container_name")
            if legacy_name:
                replicas = [{
                    "replica_id": 0,
                    "container_name": legacy_name,
                    "host_port": None,
                }]
        current = len(replicas)
        if desired == current:
            return current, current

        image_ref = state.get("image_ref")
        if not image_ref:
            raise ValueError("install_state.json missing image_ref")
        restart_policy = state.get("restart_policy", "on-failure")
        restart_max_retries = int(state.get("restart_max_retries", 5))

        if desired > current:
            # Scale up — spawn additional replicas with consecutive ids.
            existing_ids = {r["replica_id"] for r in replicas}
            next_id = max(existing_ids) + 1 if existing_ids else 0
            spawn_logs: list[str] = []
            for _ in range(desired - current):
                container_name = self._container_name(
                    plugin_id, next_id, replica_count=desired,
                )
                port_key = self._port_key(plugin_id, next_id)
                host_port = self._port_allocator.allocate(port_key)
                http_endpoint = f"http://127.0.0.1:{host_port}"
                self._docker_run(
                    container_name, image_ref, runtime, spawn_logs,
                    host_port=host_port, http_endpoint=http_endpoint,
                    restart_policy=restart_policy,
                    restart_max_retries=restart_max_retries,
                )
                replicas.append({
                    "replica_id": next_id,
                    "container_name": container_name,
                    "host_port": host_port,
                })
                next_id += 1
        else:
            # Scale down — stop+rm the highest-replica_id containers.
            # RMQ requeues unacked work to the survivors (warn-and-
            # proceed per Wave 4 plan).
            replicas.sort(key=lambda r: r["replica_id"])
            to_remove = replicas[desired:]
            replicas = replicas[:desired]
            for replica in to_remove:
                name = replica.get("container_name")
                if name:
                    self._docker_stop_rm(name, swallow=True)
                self._port_allocator.release(
                    self._port_key(plugin_id, replica["replica_id"]),
                )

        state["replicas"] = replicas
        state["container_name"] = replicas[0]["container_name"] if replicas else None
        self._write_state(target, state)
        return current, desired

    @staticmethod
    def _restart_flag(policy: str, max_retries: int) -> Optional[str]:
        """Map manifest restart_policy + restart_max_retries to docker's
        ``--restart`` flag value.

        ``on-failure`` with ``max_retries=0`` drops the cap (infinite),
        matching docker's own semantics. ``no`` returns ``None`` so the
        flag is omitted entirely — docker's implicit default is ``no``,
        but being explicit is friendlier for ``docker inspect``.
        """
        if policy == "no":
            return "no"
        if policy == "on-failure":
            if max_retries > 0:
                return f"on-failure:{max_retries}"
            return "on-failure"
        if policy in ("always", "unless-stopped"):
            return policy
        # Defense in depth: an unknown policy should have been rejected
        # by the manifest validator. Fall back to ``on-failure``.
        return "on-failure"

    def _container_gpfs_root(self, host_gpfs_root: str) -> str:
        """Return the in-container path for the shared GPFS root."""
        normalized = host_gpfs_root.replace("\\", "/")
        if len(normalized) > 1 and normalized[1] == ":":
            return "/gpfs"
        return normalized

    def _docker_stop_rm(self, container_name: str, *, swallow: bool) -> None:
        """``docker stop`` followed by ``docker rm``.

        ``stop`` is a no-op on an already-exited container; ``rm``
        is what actually frees the name. Both run unconditionally
        so callers don't have to know the container's state.

        ``swallow=True`` is for the install-rollback path where any
        cleanup error is logged-not-raised — the install already
        failed, no point throwing on cleanup too.
        """
        for cmd in (
            [self.docker_command, "stop", container_name],
            [self.docker_command, "rm", container_name],
        ):
            result = self._run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                msg = f"{' '.join(cmd)} failed: {result.stderr or result.stdout}"
                if swallow:
                    logger.warning(msg)
                else:
                    raise RuntimeError(msg)

    def _docker_rmi(self, image_ref: str, *, swallow: bool) -> None:
        cmd = [self.docker_command, "rmi", image_ref]
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            msg = f"docker rmi {image_ref} failed: {result.stderr or result.stdout}"
            if swallow:
                logger.warning(msg)
            else:
                raise RuntimeError(msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _container_name(
        self, plugin_id: str, replica_id: int = 0, replica_count: int = 1,
    ) -> str:
        """Container name for a replica.

        Single-replica installs keep the legacy name shape
        ``magellon-plugin-<id>`` so pre-Wave-4 state files + UI lookups
        keep working. Multi-replica installs append ``-<i>`` (zero-
        indexed) so docker's unique-name requirement is satisfied.
        """
        # plugin_id is already validated as [a-z0-9._-]+ by the
        # manifest model, so it's directly usable as a container
        # name segment.
        base = f"magellon-plugin-{plugin_id}"
        if replica_count <= 1 and replica_id == 0:
            return base
        return f"{base}-{replica_id}"

    @staticmethod
    def _port_key(plugin_id: str, replica_id: int) -> str:
        """Per-replica key for :class:`PluginPortAllocator`. Replica 0
        uses the bare plugin_id so existing single-replica installs
        keep their previously-allocated port across an upgrade to
        Wave 4 — only replicas > 0 get suffixed keys."""
        if replica_id == 0:
            return plugin_id
        return f"{plugin_id}#{replica_id}"

    def _built_image_tag(self, manifest: PluginArchiveManifest) -> str:
        # Local-only tag for built images; namespaced so it's clearly
        # ours and won't collide with pulled images.
        return f"magellon-plugin-{manifest.plugin_id}:{manifest.version}"

    def _extract_archive(self, archive_path: Path, target: Path) -> None:
        with zipfile.ZipFile(archive_path) as z:
            for name in z.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RuntimeError(f"unsafe archive entry: {name!r}")
            z.extractall(target)

    def _write_state(self, target: Path, state: Dict) -> None:
        (target / STATE_FILENAME).write_text(
            json.dumps(state, indent=2), encoding="utf-8",
        )

    def _read_state(self, target: Path) -> Dict:
        return json.loads((target / STATE_FILENAME).read_text(encoding="utf-8"))


__all__ = ["DockerInstaller", "STATE_FILENAME"]

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
        container_started = False
        container_name = self._container_name(plugin_id)

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

            # 3. Allocate a host port + run the container.
            host_port = self._port_allocator.allocate(plugin_id)
            http_endpoint = f"http://127.0.0.1:{host_port}"
            logs.append(f"allocated host port {host_port} → {http_endpoint}")
            self._docker_run(
                container_name, image_ref, runtime, logs,
                host_port=host_port, http_endpoint=http_endpoint,
            )
            container_started = True

            # 4. Write state for uninstall to find later.
            self._write_state(target, {
                "plugin_id": plugin_id,
                "version": manifest.version,
                "method": "docker",
                "image_ref": image_ref,
                "image_was_built": image_was_built,
                "container_name": container_name,
            })

            return InstallResult(
                success=True,
                plugin_id=plugin_id,
                install_method=self.method,
                install_dir=target,
                logs="\n".join(logs),
            )

        except Exception as exc:  # noqa: BLE001
            # Roll back in reverse order — each step is best-effort
            # because a failure at step N might mean step N-1 didn't
            # actually finish either.
            if container_started:
                self._docker_stop_rm(container_name, swallow=True)
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

        # 1. Stop + remove container (always, even if already stopped).
        try:
            self._docker_stop_rm(state["container_name"], swallow=False)
        except Exception as exc:  # noqa: BLE001
            return UninstallResult(
                success=False,
                plugin_id=plugin_id,
                error=f"docker stop/rm failed: {exc}",
            )

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
    ) -> None:
        cmd = [
            self.docker_command, "run",
            "-d",  # detached
            "--name", container_name,
        ]
        if self.network:
            cmd.extend(["--network", self.network])
        # R2 #4: publish the host's allocated port → container's
        # FastAPI port. CoreService reaches the plugin at
        # ``http://127.0.0.1:<host_port>``; the container itself
        # binds the conventional 8000.
        if host_port is not None:
            cmd.extend(["-p", f"{host_port}:{self.container_port}"])
        # Mount the GPFS root at the same path inside the container —
        # plugins read/write there per DATA_PLANE.md, and the same
        # absolute path being valid inside and out is what makes
        # MAGELLON_HOME_DIR portable.
        cmd.extend(["-v", f"{runtime.gpfs_root}:{runtime.gpfs_root}"])
        # Deployment-supplied env vars.
        cmd.extend(["-e", f"MAGELLON_BROKER_URL={runtime.broker_url}"])
        cmd.extend(["-e", f"MAGELLON_HOME_DIR={runtime.gpfs_root}"])
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

    def _container_name(self, plugin_id: str) -> str:
        # plugin_id is already validated as [a-z0-9._-]+ by the
        # manifest model, so it's directly usable as a container
        # name segment.
        return f"magellon-plugin-{plugin_id}"

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

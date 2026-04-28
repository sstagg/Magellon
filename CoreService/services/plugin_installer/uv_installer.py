"""``UvInstaller`` — installs pure-Python plugins via ``uv`` (P4).

Per-plugin layout under ``<plugins_dir>/<plugin_id>/``::

    <plugin_id>/
    ├── manifest.yaml         (extracted from .mpn)
    ├── plugin.yaml           (legacy alias, also extracted)
    ├── pyproject.toml        (or requirements.txt)
    ├── main.py
    ├── plugin/
    ├── schemas/
    ├── .venv/                (uv-built isolated environment)
    └── runtime.env           (deployment-supplied values)

Each plugin gets its OWN venv. A plugin pinning ``numpy<1.20`` must
not downgrade CoreService's numpy or another plugin's. uv handles
the venv build and dependency resolution.

Process lifecycle is intentionally separate from install: this class
unpacks + builds the venv + writes runtime.env, but does NOT spawn
the plugin process by default. Callers (the manager, in production)
launch it after install — separating these concerns keeps unit
tests cheap (no subprocess explosion) and lets the spawn path be
swapped (systemd, supervisord, plain Popen) without changing the
installer.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, List, Optional

from magellon_sdk.archive.manifest import InstallSpec, PluginArchiveManifest

from services.plugin_installer.predicates import HostInfo, evaluate_predicates
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)

logger = logging.getLogger(__name__)


# Default subprocess runner — overridable so unit tests can stub uv
# without invoking it for real.
SubprocessRunner = Callable[..., subprocess.CompletedProcess]


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


def _venv_python_path(venv_dir: Path) -> Path:
    """Cross-platform path to the venv's Python interpreter."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


class UvInstaller:
    """Installer impl for the ``uv`` install method."""

    method = "uv"

    def __init__(
        self,
        plugins_dir: Path,
        *,
        uv_command: str = "uv",
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
        verify_checksums: bool = True,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.uv_command = uv_command
        self._run = subprocess_runner
        self.verify_checksums = verify_checksums

    # ------------------------------------------------------------------
    # Installer Protocol
    # ------------------------------------------------------------------

    def supports(self, install_spec: InstallSpec, host: HostInfo) -> List[str]:
        if install_spec.method != "uv":
            return [f"method != uv (got {install_spec.method!r})"]
        if not install_spec.pyproject:
            return ["uv install spec missing pyproject"]
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
                error=f"plugin {plugin_id} already installed at {target} — "
                      f"uninstall first or use upgrade",
            )

        target.mkdir(parents=True)
        logs: list[str] = []

        try:
            # 1. Extract archive.
            self._extract_archive(archive_path, target)
            logs.append(f"extracted {archive_path} -> {target}")

            # 2. Verify file checksums (best effort — a regression in
            #    pack would otherwise be invisible until plugin runtime).
            if self.verify_checksums:
                bad = self._verify_checksums(target, manifest)
                if bad:
                    raise RuntimeError(
                        f"checksum mismatch on {len(bad)} file(s): {bad[:3]}"
                    )
                logs.append("checksums verified")

            # 3. Build the venv.
            venv_dir = target / ".venv"
            self._uv_venv(venv_dir, logs)

            # 4. Install dependencies. The manifest's pyproject path
            # is the canonical source; falls back to common defaults
            # for v0 plugins that don't declare it explicitly.
            self._uv_install_deps(target, venv_dir, install_spec.pyproject, logs)

            # 5. Write runtime.env so the plugin process / systemd unit
            #    has the deployment values.
            (target / "runtime.env").write_text(
                self._format_runtime_env(runtime), encoding="utf-8",
            )
            logs.append("wrote runtime.env")

            return InstallResult(
                success=True,
                plugin_id=plugin_id,
                install_method=self.method,
                install_dir=target,
                logs="\n".join(logs),
            )

        except Exception as exc:  # noqa: BLE001 — surface anything
            # Best-effort cleanup so a failed install doesn't leave a
            # half-written directory blocking the next attempt.
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

        # uv installs are pure filesystem (we don't currently spawn a
        # process at install time). For preserve_as_backup we rename
        # rather than delete so the upgrade flow can restore on
        # failure. The version comes from the installed manifest so
        # the .bak name carries it.
        if preserve_as_backup:
            try:
                version = self._read_installed_version(target)
                backup = self.plugins_dir / f"{plugin_id}.{version}.bak"
                _replace_existing(backup)  # GC any prior .bak with same version
                target.rename(backup)
                return UninstallResult(success=True, plugin_id=plugin_id)
            except Exception as exc:  # noqa: BLE001
                return UninstallResult(
                    success=False, plugin_id=plugin_id,
                    error=f"backup rename failed: {exc}",
                )

        try:
            shutil.rmtree(target)
            return UninstallResult(success=True, plugin_id=plugin_id)
        except Exception as exc:  # noqa: BLE001
            return UninstallResult(
                success=False, plugin_id=plugin_id, error=str(exc),
            )

    def _read_installed_version(self, target: Path) -> str:
        """Look up the installed plugin's version by reading its
        manifest. Used by uninstall(preserve_as_backup=True) so the
        .bak directory name carries the version."""
        from magellon_sdk.archive.manifest import load_manifest_bytes
        for name in ("manifest.yaml", "plugin.yaml"):
            path = target / name
            if path.is_file():
                manifest = load_manifest_bytes(path.read_bytes())
                return manifest.version
        # Defensive fallback — bare directory with no manifest
        # (shouldn't happen, but if it does we don't crash uninstall).
        return "unknown"

    def is_installed(self, plugin_id: str) -> bool:
        return (self.plugins_dir / plugin_id).is_dir()

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _extract_archive(self, archive_path: Path, target: Path) -> None:
        with zipfile.ZipFile(archive_path) as z:
            # Defense against zip slip — refuse archives with absolute
            # or parent-traversal entries before extracting.
            for name in z.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RuntimeError(f"unsafe archive entry: {name!r}")
            z.extractall(target)

    def _verify_checksums(
        self, target: Path, manifest: PluginArchiveManifest,
    ) -> List[str]:
        """Return list of relative paths whose disk content doesn't
        match the manifest's checksum table. Empty = all good."""
        import hashlib

        bad: List[str] = []
        for arcname, expected in manifest.file_checksums.items():
            full = target / arcname
            if not full.exists():
                bad.append(arcname)
                continue
            h = hashlib.sha256()
            with full.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            if h.hexdigest() != expected:
                bad.append(arcname)
        return bad

    def _uv_venv(self, venv_dir: Path, logs: list[str]) -> None:
        cmd = [self.uv_command, "venv", str(venv_dir)]
        logs.append(f"+ {' '.join(cmd)}")
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"uv venv failed: {result.stderr or result.stdout}"
            )
        logs.append((result.stdout or "").rstrip())

    def _uv_install_deps(
        self,
        target: Path,
        venv_dir: Path,
        pyproject_rel: Optional[str],
        logs: list[str],
    ) -> None:
        """Install the plugin's deps into its venv.

        ``pyproject_rel`` is the manifest-declared path
        (``install[i].pyproject``). When that file exists, we
        editable-install the plugin's own package. Falls back to
        ``requirements.txt`` for v0 layouts that don't ship a
        proper pyproject.
        """
        env = {**os.environ, "VIRTUAL_ENV": str(venv_dir)}

        # Prefer the manifest-declared pyproject (relative to target).
        # If it exists, editable-install the plugin's package — that
        # makes ``main.py`` able to import siblings correctly.
        manifest_pyproject = (
            target / pyproject_rel if pyproject_rel else target / "pyproject.toml"
        )
        requirements = target / "requirements.txt"

        if manifest_pyproject.exists():
            cmd = [self.uv_command, "pip", "install", "-e", str(target)]
        elif requirements.exists():
            cmd = [self.uv_command, "pip", "install", "-r", str(requirements)]
        else:
            raise RuntimeError(
                f"neither {pyproject_rel or 'pyproject.toml'} nor requirements.txt "
                f"found — uv install has nothing to do"
            )

        logs.append(f"+ {' '.join(cmd)}")
        result = self._run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise RuntimeError(
                f"uv pip install failed: {result.stderr or result.stdout}"
            )
        logs.append((result.stdout or "").rstrip())

    def _format_runtime_env(self, runtime: RuntimeConfig) -> str:
        """Write a key=value file the plugin process loads at startup.

        We bake the deployment-supplied values here (per archive
        spec §6) instead of relying on the parent process's env —
        explicit beats implicit when an operator is debugging "why
        did this plugin pick up the wrong broker?"
        """
        lines = [
            "# Generated by UvInstaller — deployment-supplied runtime values.",
            "# Plugin process should load these via os.environ at startup.",
            "# Do NOT commit this file or copy it into archives.",
            f"MAGELLON_BROKER_URL={runtime.broker_url}",
            f"MAGELLON_HOME_DIR={runtime.gpfs_root}",
        ]
        for k, v in sorted(runtime.extra_env.items()):
            lines.append(f"{k}={v}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Public helpers callers may use after install
    # ------------------------------------------------------------------

    def venv_python(self, plugin_id: str) -> Optional[Path]:
        """Path to the installed plugin's Python interpreter, or
        ``None`` if not installed. The manager / launcher uses this
        to spawn the plugin process."""
        target = self.plugins_dir / plugin_id
        if not target.is_dir():
            return None
        return _venv_python_path(target / ".venv")

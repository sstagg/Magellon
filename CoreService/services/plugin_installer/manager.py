"""``PluginInstallManager`` — install pipeline orchestrator (P4).

Validates an archive, picks the first install method the host
supports, dispatches to the matching :class:`Installer`. Doesn't
itself extract or run uv/docker — that's the installer's job.

Health-check is configurable: production wires it to the liveness
registry (wait for the plugin to announce within
``manifest.health_check.timeout_seconds``); unit tests pass a stub.
P4 ships a no-op default so install-completes-but-plugin-not-running
isn't reported as a failure when no bus is configured.
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from magellon_sdk.archive.manifest import (
    InstallSpec,
    PluginArchiveManifest,
    load_manifest_bytes,
)

from services.plugin_installer.predicates import (
    HostInfo,
    collect_required_binaries,
    detect_host_info,
)
from services.plugin_installer.protocol import (
    InstallResult,
    Installer,
    RuntimeConfig,
    UninstallResult,
)

logger = logging.getLogger(__name__)


# Health check signature: (plugin_id, timeout_seconds) -> announced?
HealthCheck = Callable[[str, float], bool]


def _no_health_check(plugin_id: str, timeout_seconds: float) -> bool:
    """Default health check — assumes success. Production wires to
    the liveness registry; this lets unit tests skip the bus."""
    return True


class PluginInstallManager:
    """Orchestrates install + uninstall across multiple Installer impls."""

    CANONICAL_MANIFEST = "manifest.yaml"
    LEGACY_MANIFEST = "plugin.yaml"

    def __init__(
        self,
        installers: List[Installer],
        *,
        host_info_provider: Optional[Callable[[List[str]], HostInfo]] = None,
        health_check: HealthCheck = _no_health_check,
    ) -> None:
        # Index by method for quick lookup. If two installers claim
        # the same method, the LAST wins (lets a deployment override
        # the default impl by appending its own).
        self._installers: Dict[str, Installer] = {}
        for inst in installers:
            self._installers[inst.method] = inst
        self._host_info_provider = host_info_provider or detect_host_info
        self._health_check = health_check

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(
        self, archive_path: Path, runtime: RuntimeConfig,
    ) -> InstallResult:
        # 1. Read + validate manifest.
        try:
            manifest = self._load_manifest(archive_path)
        except Exception as exc:  # noqa: BLE001
            return InstallResult(
                success=False,
                plugin_id="",
                install_method="",
                error=f"manifest load/validate failed: {exc}",
            )

        # 2. Probe host capabilities once (with the manifest's binary
        #    needs as the probe set so we don't enumerate all of PATH).
        required_binaries = collect_required_binaries(
            [s.requires for s in manifest.install]
        )
        host = self._host_info_provider(required_binaries)

        # 3. Pick the first install method whose predicates pass.
        chosen = self._pick_installer(manifest, host)
        if chosen is None:
            return InstallResult(
                success=False,
                plugin_id=manifest.plugin_id,
                install_method="",
                error=self._explain_no_match(manifest, host),
            )
        spec, installer = chosen

        # 4. Refuse if already installed under this or any installer.
        for inst in self._installers.values():
            if inst.is_installed(manifest.plugin_id):
                return InstallResult(
                    success=False,
                    plugin_id=manifest.plugin_id,
                    install_method=inst.method,
                    error=f"plugin {manifest.plugin_id} already installed via "
                          f"{inst.method}; use upgrade to replace",
                )

        # 5. Dispatch.
        result = installer.install(archive_path, manifest, spec, runtime)
        if not result.success:
            return result

        # 6. Health check — wait for announce, or skip if no-op.
        timeout = float(manifest.health_check.timeout_seconds)
        if manifest.health_check.expected_announce:
            announced = self._health_check(manifest.plugin_id, timeout)
            if not announced:
                # Roll back — an installed-but-dead plugin is worse
                # than no plugin (operators see stale state).
                installer.uninstall(manifest.plugin_id)
                return InstallResult(
                    success=False,
                    plugin_id=manifest.plugin_id,
                    install_method=installer.method,
                    error=f"plugin did not announce within {timeout}s; "
                          f"rolled back",
                    logs=result.logs,
                )

        return result

    # ------------------------------------------------------------------
    # Uninstall
    # ------------------------------------------------------------------

    def uninstall(self, plugin_id: str) -> UninstallResult:
        """Find the installer that owns this plugin and dispatch.

        We don't store install-method per plugin; instead we ask each
        installer ``is_installed(plugin_id)``. Cheap (filesystem
        check) and works even if the in-memory state was lost
        (CoreService restart between install and uninstall)."""
        for installer in self._installers.values():
            if installer.is_installed(plugin_id):
                return installer.uninstall(plugin_id)
        return UninstallResult(
            success=False,
            plugin_id=plugin_id,
            error=f"plugin {plugin_id} not installed",
        )

    def is_installed(self, plugin_id: str) -> bool:
        return any(
            i.is_installed(plugin_id) for i in self._installers.values()
        )

    def list_installed(self) -> Dict[str, str]:
        """Return ``{plugin_id: install_method}`` across every
        installer. Useful for the admin endpoint's ``GET /admin/plugins/installed``."""
        # NOTE: each Installer doesn't expose its inventory by name
        # in this minimal P4 surface. We return what's discoverable
        # at the filesystem layer for installers that materialize a
        # directory; richer impls can enrich this in P7.
        out: Dict[str, str] = {}
        for installer in self._installers.values():
            base = getattr(installer, "plugins_dir", None)
            if isinstance(base, Path) and base.is_dir():
                for child in base.iterdir():
                    if child.is_dir() and installer.is_installed(child.name):
                        out[child.name] = installer.method
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_manifest(self, archive_path: Path) -> PluginArchiveManifest:
        with zipfile.ZipFile(archive_path) as z:
            for name in (self.CANONICAL_MANIFEST, self.LEGACY_MANIFEST):
                try:
                    with z.open(name) as f:
                        return load_manifest_bytes(f.read())
                except KeyError:
                    continue
        raise FileNotFoundError(
            f"archive {archive_path} contains neither "
            f"{self.CANONICAL_MANIFEST} nor {self.LEGACY_MANIFEST}"
        )

    def _pick_installer(
        self, manifest: PluginArchiveManifest, host: HostInfo,
    ) -> Optional[Tuple[InstallSpec, Installer]]:
        for spec in manifest.install:
            installer = self._installers.get(spec.method)
            if installer is None:
                continue
            failures = installer.supports(spec, host)
            if not failures:
                return spec, installer
        return None

    def _explain_no_match(
        self, manifest: PluginArchiveManifest, host: HostInfo,
    ) -> str:
        """Build a debug-friendly message listing every install
        method's failed predicates. Operators staring at
        "no installer matches" otherwise have no idea why."""
        lines = [
            f"no install method matched host for plugin {manifest.plugin_id!r}:"
        ]
        for i, spec in enumerate(manifest.install):
            installer = self._installers.get(spec.method)
            if installer is None:
                lines.append(
                    f"  [{i}] method={spec.method!r}: no installer registered"
                )
                continue
            failures = installer.supports(spec, host)
            joined = "; ".join(failures) if failures else "(no failures)"
            lines.append(f"  [{i}] method={spec.method!r}: {joined}")
        return "\n".join(lines)

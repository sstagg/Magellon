"""``PluginInstallManager`` — install pipeline orchestrator (P4 + P6).

Validates an archive, picks the first install method the host
supports, dispatches to the matching :class:`Installer`. Doesn't
itself extract or run uv/docker — that's the installer's job.

Health-check is configurable: production wires it to the liveness
registry (wait for the plugin to announce within
``manifest.health_check.timeout_seconds``); unit tests pass a stub.
P4 ships a no-op default so install-completes-but-plugin-not-running
isn't reported as a failure when no bus is configured.

Upgrade flow (P6)
-----------------

``upgrade(plugin_id, new_archive, runtime)`` is a guarded swap:

  1. Validate the new archive's plugin_id matches the installed one
     and version is strictly newer (override with ``force_downgrade``).
  2. ``uninstall(plugin_id, preserve_as_backup=True)`` — old install
     is renamed to ``<plugin_id>.<old_version>.bak/``; container
     stopped, image preserved.
  3. ``install(new_archive, runtime)`` — fresh install of the new
     version into the now-empty ``<plugin_id>/`` slot.
  4. If install fails, attempt rollback: rename .bak back to
     ``<plugin_id>``. The plugin is still down (we don't auto-respawn),
     but the on-disk state is restored so an operator can recover.
  5. Stale .bak directories from prior upgrades are removed at the
     start of each upgrade — only the current version's pre-upgrade
     state is kept.

The plan calls for "5 in-flight tasks finish on old, 6th onward on
new" with overlapping containers. That requires a "drain"
signal we don't have on the bus today; for now upgrade is
stop-then-install. RMQ requeues unacked messages from the killed
old container so in-flight tasks aren't lost — they re-run on the
new version. A future drain primitive (post-P9) can layer on top.
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
from magellon_sdk.archive.manifest import _parse_version  # type: ignore[attr-defined]

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


def _is_strictly_newer(candidate: str, baseline: str) -> bool:
    """SemVer-style "candidate > baseline". Used by upgrade to refuse
    downgrades. If either version isn't parseable, we return False
    (refuse the upgrade) — operator can still pass force_downgrade
    to bypass."""
    try:
        return _parse_version(candidate) > _parse_version(baseline)
    except (ValueError, TypeError):
        return False


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

    # ------------------------------------------------------------------
    # Upgrade (P6)
    # ------------------------------------------------------------------

    def upgrade(
        self,
        plugin_id: str,
        new_archive_path: Path,
        runtime: RuntimeConfig,
        *,
        force_downgrade: bool = False,
    ) -> InstallResult:
        """Replace an installed plugin with a different-versioned
        archive.

        Returns the install-side ``InstallResult``: ``.success=True``
        means the new version is live; on ``False`` the old version
        has been restored from ``.bak`` (or the system is in a
        partial state, described in ``error``).
        """
        # 1. Find the owning installer + capture the old version.
        old_installer = self._find_installer_for(plugin_id)
        if old_installer is None:
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method="",
                error=f"plugin {plugin_id!r} not installed; use install instead",
            )

        old_version = self._read_installed_version(old_installer, plugin_id)
        if old_version is None:
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method=old_installer.method,
                error=f"plugin {plugin_id!r}: cannot read installed manifest "
                      f"to determine current version",
            )

        # 2. Load + validate the new archive.
        try:
            new_manifest = self._load_manifest(new_archive_path)
        except Exception as exc:  # noqa: BLE001
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method="",
                error=f"new archive invalid: {exc}",
            )
        if new_manifest.plugin_id != plugin_id:
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method="",
                error=f"new archive's plugin_id is {new_manifest.plugin_id!r}, "
                      f"but upgrade target is {plugin_id!r}",
            )

        # 3. Version-monotonicity check — refuse downgrades unless
        #    explicitly forced. SemVer-style; non-parseable versions
        #    bypass the check (defensive — better to install than
        #    refuse on a custom version string).
        if not force_downgrade and not _is_strictly_newer(
            new_manifest.version, old_version,
        ):
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method="",
                error=f"new version {new_manifest.version!r} is not newer "
                      f"than installed {old_version!r}; pass "
                      f"force_downgrade=True to override",
            )

        # 4. GC any stale .bak from prior upgrades — keep only the
        #    one this upgrade is about to create.
        self._gc_stale_backups(plugin_id)

        # 5. Move the old install to .bak (container/process stops here).
        backup_result = old_installer.uninstall(
            plugin_id, preserve_as_backup=True,
        )
        if not backup_result.success:
            return InstallResult(
                success=False,
                plugin_id=plugin_id,
                install_method=old_installer.method,
                error=f"could not back up old install: {backup_result.error}",
            )

        # 6. Install the new version.
        install_result = self.install(new_archive_path, runtime)
        if install_result.success:
            return install_result

        # 7. New install failed — try to roll back.
        rollback_note = self._restore_backup(
            plugin_id, old_version, old_installer,
        )
        return InstallResult(
            success=False,
            plugin_id=plugin_id,
            install_method=install_result.install_method,
            error=(
                f"new version install failed; "
                f"{install_result.error}\nrollback: {rollback_note}"
            ),
            logs=install_result.logs,
        )

    # ------------------------------------------------------------------
    # Upgrade helpers
    # ------------------------------------------------------------------

    def _find_installer_for(self, plugin_id: str) -> Optional[Installer]:
        for installer in self._installers.values():
            if installer.is_installed(plugin_id):
                return installer
        return None

    def _read_installed_version(
        self, installer: Installer, plugin_id: str,
    ) -> Optional[str]:
        """Both UvInstaller and DockerInstaller install under
        ``installer.plugins_dir/<plugin_id>/`` and ship a
        ``manifest.yaml`` there. Read the version from it.

        We don't add this to the Protocol because not every future
        installer will materialize a directory (e.g. a remote-host
        installer might track state elsewhere); the duck-typed read
        is the simplest path that covers what we have today.
        """
        plugins_dir = getattr(installer, "plugins_dir", None)
        if not isinstance(plugins_dir, Path):
            return None
        for name in ("manifest.yaml", "plugin.yaml"):
            path = plugins_dir / plugin_id / name
            if path.is_file():
                try:
                    return load_manifest_bytes(path.read_bytes()).version
                except Exception:  # noqa: BLE001
                    return None
        return None

    def _gc_stale_backups(self, plugin_id: str) -> None:
        """Remove any pre-existing ``<plugin_id>.<version>.bak/``
        directories before a new upgrade creates one. Keeps just the
        most recent pre-upgrade state on disk; older backups would
        otherwise accumulate across upgrade cycles."""
        import shutil
        for installer in self._installers.values():
            plugins_dir = getattr(installer, "plugins_dir", None)
            if not isinstance(plugins_dir, Path) or not plugins_dir.is_dir():
                continue
            for child in plugins_dir.iterdir():
                if (
                    child.is_dir()
                    and child.name.startswith(f"{plugin_id}.")
                    and child.name.endswith(".bak")
                ):
                    shutil.rmtree(child, ignore_errors=True)

    def _restore_backup(
        self, plugin_id: str, old_version: str, old_installer: Installer,
    ) -> str:
        """Best-effort rollback after a failed upgrade — rename the
        ``.bak`` directory back to ``<plugin_id>``. Returns a one-line
        status note for the operator. Does NOT respawn the plugin
        (we don't have a generic ``start()`` yet); operator's
        responsibility to restart after rollback."""
        plugins_dir = getattr(old_installer, "plugins_dir", None)
        if not isinstance(plugins_dir, Path):
            return "rollback skipped: installer has no plugins_dir"
        backup = plugins_dir / f"{plugin_id}.{old_version}.bak"
        target = plugins_dir / plugin_id
        if not backup.is_dir():
            return f"rollback failed: {backup} missing"
        if target.exists():
            # New install left some residue. Best-effort: blow it away
            # so the rename can land.
            import shutil
            shutil.rmtree(target, ignore_errors=True)
        try:
            backup.rename(target)
        except Exception as exc:  # noqa: BLE001
            return f"rollback failed: {exc}"
        return (
            f"old install restored at {target} (process not auto-respawned; "
            f"operator must restart)"
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

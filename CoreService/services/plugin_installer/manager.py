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
from typing import Callable, ClassVar, Dict, List, Optional, Tuple

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
    ScalableInstaller,
    UninstallResult,
)
from services.plugin_installer.lifecycle import (
    BackendLifecycle,
    LifecycleResult,
    LifecycleStatus,
    NotSupportedError,
    UvLifecycle,
)
from services.plugin_installer.supervisor import (
    NoOpSupervisor,
    Supervisor,
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
        host_info_provider: Optional[Callable[..., HostInfo]] = None,
        health_check: HealthCheck = _no_health_check,
        supervisor: Optional[Supervisor] = None,
        lifecycles: Optional[List[BackendLifecycle]] = None,
    ) -> None:
        # Index by method for quick lookup. If two installers claim
        # the same method, the LAST wins (lets a deployment override
        # the default impl by appending its own).
        self._installers: Dict[str, Installer] = {}
        for inst in installers:
            self._installers[inst.method] = inst
        self._host_info_provider = host_info_provider or detect_host_info
        self._health_check = health_check
        # Supervisor is optional and defaults to NoOp so manager unit
        # tests don't shell out. Production wires SystemdUserSupervisor
        # via the factory.
        self._supervisor: Supervisor = supervisor or NoOpSupervisor()
        # Method-indexed lifecycle (Phase 1). When ``lifecycles`` is
        # omitted, we synthesize a UvLifecycle wrapping the existing
        # ``_supervisor`` so pre-Phase-1 callers see no behaviour change.
        # Docker plugins need an explicit DockerLifecycle in the list.
        self._lifecycles: Dict[str, BackendLifecycle] = {}
        if lifecycles is not None:
            for lc in lifecycles:
                self._lifecycles[lc.method] = lc
        if "uv" not in self._lifecycles:
            self._lifecycles["uv"] = UvLifecycle(self._supervisor)

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(
        self,
        archive_path: Path,
        runtime: RuntimeConfig,
        *,
        preferred_method: Optional[str] = None,
    ) -> InstallResult:
        """Install a plugin from a ``.mpn`` archive.

        ``preferred_method`` (e.g. ``"uv"`` / ``"docker"``) lets the
        operator pin a specific install method instead of letting the
        manager auto-pick. When set, the manager only considers that
        method's spec; if its predicates fail or no spec for that
        method exists, the install fails with an actionable error
        instead of falling back to a different method silently. When
        ``None`` (the default + back-compat path) the manager picks
        the first method whose predicates pass.
        """
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
        host = self._host_info_provider(probe_binaries=required_binaries)

        # 3. Pick the install method.
        if preferred_method:
            chosen = self._pick_installer(
                manifest, host, only_method=preferred_method,
            )
            if chosen is None:
                return InstallResult(
                    success=False,
                    plugin_id=manifest.plugin_id,
                    install_method=preferred_method,
                    error=self._explain_preferred_unmatched(
                        manifest, host, preferred_method,
                    ),
                )
        else:
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

        # 4a. Replica-method gate (Wave 4 / manifest v1.1).
        # uv plugins are pinned to single-instance — uv replicas need
        # N ports + N working dirs and aren't worth the complexity for
        # the dev-on-laptop case (locked-in scope per the Wave 4 plan).
        rep_gate = self._check_replicas_supported(installer.method, manifest)
        if rep_gate is not None:
            return InstallResult(
                success=False, plugin_id=manifest.plugin_id,
                install_method=installer.method, error=rep_gate,
            )

        # 4b. Restart-policy gate (Wave 4 / manifest v1.1).
        # uv-Popen plugins can't honor any policy other than 'no' — we
        # don't ship a watchdog thread. Refuse here BEFORE spending the
        # install pipeline rather than letting the policy silently
        # become a no-op at runtime.
        gate = self._check_restart_policy_supported(installer.method, manifest)
        if gate is not None:
            return InstallResult(
                success=False,
                plugin_id=manifest.plugin_id,
                install_method=installer.method,
                error=gate,
            )

        # 5. Dispatch.
        result = installer.install(archive_path, manifest, spec, runtime)
        if not result.success:
            return result

        # 6. Supervisor: write systemd unit + start the plugin (PI-2).
        # Only relevant for installers that materialize a directory
        # (uv); docker installers manage their own container lifecycle
        # and skip supervision.
        if installer.method == "uv" and result.install_dir is not None:
            sup_install = self._supervisor.install_unit(
                manifest.plugin_id, result.install_dir,
                restart_policy=manifest.lifecycle.restart_policy,
                restart_max_retries=manifest.lifecycle.restart_max_retries,
            )
            if not sup_install.success:
                # Best-effort rollback — leaving a half-supervised
                # install is worse than rolling back.
                installer.uninstall(manifest.plugin_id)
                return InstallResult(
                    success=False,
                    plugin_id=manifest.plugin_id,
                    install_method=installer.method,
                    error=f"supervisor install_unit failed: {sup_install.error}",
                    logs=result.logs,
                )
            sup_start = self._supervisor.start(manifest.plugin_id)
            if not sup_start.success:
                self._supervisor.remove_unit(manifest.plugin_id)
                installer.uninstall(manifest.plugin_id)
                return InstallResult(
                    success=False,
                    plugin_id=manifest.plugin_id,
                    install_method=installer.method,
                    error=f"supervisor start failed: {sup_start.error}",
                    logs=result.logs,
                )

        # 7. Health check — wait for announce, or skip if no-op.
        timeout = float(manifest.health_check.timeout_seconds)
        if manifest.health_check.expected_announce:
            announced = self._health_check(manifest.plugin_id, timeout)
            if not announced:
                # Roll back — an installed-but-dead plugin is worse
                # than no plugin (operators see stale state).
                if installer.method == "uv":
                    self._supervisor.stop(manifest.plugin_id)
                    self._supervisor.remove_unit(manifest.plugin_id)
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
                # Stop + remove the supervisor unit before reclaiming
                # the install dir — otherwise systemd holds open file
                # descriptors and the rmtree fails on Linux.
                if installer.method == "uv":
                    self._supervisor.stop(plugin_id)
                    self._supervisor.remove_unit(plugin_id)
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
    # Lifecycle (run / pause / stop) — delegate to supervisor
    # ------------------------------------------------------------------

    # Typed dispatch table — replaces `getattr(lc, verb)` so a typo on
    # the call site is a NameError, not a runtime AttributeError.
    _LIFECYCLE_VERBS: ClassVar[Dict[str, Callable[[BackendLifecycle, str], LifecycleResult]]] = {
        "start": lambda lc, pid: lc.start(pid),
        "stop": lambda lc, pid: lc.stop(pid),
        "restart": lambda lc, pid: lc.restart(pid),
        "pause": lambda lc, pid: lc.pause(pid),
        "unpause": lambda lc, pid: lc.unpause(pid),
    }

    def _route_lifecycle(self, plugin_id: str, verb: str) -> LifecycleResult:
        """Look up the owning installer's method, dispatch ``verb`` on
        the matching lifecycle. Unsupported verbs (pause on uv) bubble
        up as :class:`NotSupportedError` so the controller can map to
        HTTP 409.
        """
        installer = self._find_installer_for(plugin_id)
        if installer is None:
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                error=f"plugin {plugin_id} not installed",
            )
        lc = self._lifecycles.get(installer.method)
        if lc is None:
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                error=f"no lifecycle controller for install method "
                      f"{installer.method!r}",
            )
        fn = self._LIFECYCLE_VERBS.get(verb)
        if fn is None:
            raise ValueError(
                f"unknown lifecycle verb {verb!r}; valid: "
                f"{sorted(self._LIFECYCLE_VERBS)}",
            )
        return fn(lc, plugin_id)

    def start(self, plugin_id: str) -> LifecycleResult:
        """Launch the installed plugin's process / container.

        Routes via the owning installer's method:
          - ``uv`` → systemd-user / Popen via the wrapped supervisor.
          - ``docker`` → ``docker start <container_name>`` via DockerLifecycle.

        Idempotent: starting an already-running plugin returns success.
        """
        return self._route_lifecycle(plugin_id, "start")

    def stop(self, plugin_id: str) -> LifecycleResult:
        """Stop the plugin's process / container. Idempotent."""
        return self._route_lifecycle(plugin_id, "stop")

    def restart(self, plugin_id: str) -> LifecycleResult:
        """Stop + start. Docker uses ``docker restart`` natively; uv
        does stop-then-start since systemd-user reload semantics aren't
        what we want for a code update."""
        return self._route_lifecycle(plugin_id, "restart")

    def pause(self, plugin_id: str) -> LifecycleResult:
        """Pause the plugin (docker-only). uv raises NotSupportedError
        which the controller maps to HTTP 409."""
        return self._route_lifecycle(plugin_id, "pause")

    def unpause(self, plugin_id: str) -> LifecycleResult:
        """Resume a paused plugin. Same constraint as ``pause``."""
        return self._route_lifecycle(plugin_id, "unpause")

    def logs(self, plugin_id: str, *, tail: int = 200) -> str:
        """Return the last ``tail`` lines from the plugin's log source.

        Routes via the owning installer's method same as the other
        lifecycle verbs. Returns an empty string if the plugin isn't
        installed or the backend lifecycle can't produce logs.
        """
        installer = self._find_installer_for(plugin_id)
        if installer is None:
            return ""
        lc = self._lifecycles.get(installer.method)
        if lc is None:
            return ""
        try:
            return lc.logs(plugin_id, tail=tail)
        except Exception as exc:  # noqa: BLE001
            return f"<lifecycle.logs raised: {exc}>"

    def supports_pause(self, plugin_id: str) -> bool:
        """Whether the owning lifecycle declares pause support. Used
        by the catalog endpoint so the UI can grey out the Pause button
        for uv-installed plugins instead of letting the operator click
        and 409."""
        installer = self._find_installer_for(plugin_id)
        if installer is None:
            return False
        lc = self._lifecycles.get(installer.method)
        if lc is None:
            return False
        return bool(getattr(lc, "supports_pause", False))

    def status(self, plugin_id: str) -> LifecycleStatus:
        """Coarse running / stopped / paused / unknown state."""
        installer = self._find_installer_for(plugin_id)
        if installer is None:
            return LifecycleStatus.UNKNOWN
        lc = self._lifecycles.get(installer.method)
        if lc is None:
            return LifecycleStatus.UNKNOWN
        return lc.status(plugin_id)

    def is_running(self, plugin_id: str) -> bool:
        """Best-effort liveness check. Returns False on UNKNOWN — the
        old supervisor-shaped semantics."""
        return self.status(plugin_id) == LifecycleStatus.RUNNING

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
        preferred_method: Optional[str] = None,
    ) -> InstallResult:
        """Replace an installed plugin with a different-versioned
        archive.

        ``preferred_method`` is forwarded to the underlying install
        step and follows the same rules as :meth:`install`. When
        omitted, the manager auto-picks. (Note: this is independent
        of the *old* install's method — an upgrade is free to switch
        from ``uv`` to ``docker`` if the operator pins it.)

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
        install_result = self.install(
            new_archive_path, runtime, preferred_method=preferred_method,
        )
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

    def _check_replicas_supported(
        self, install_method: str, manifest: PluginArchiveManifest,
    ) -> Optional[str]:
        """Refuse manifests that ask for replicas on a non-docker
        install method. Docker spawns N containers; uv doesn't have
        the N-port / N-working-dir plumbing.

        ``replicas.desired == 1`` is always OK regardless of method.
        """
        if manifest.resources.replicas is None:
            return None
        desired = manifest.resources.replicas.desired
        if desired <= 1:
            return None
        if install_method == "docker":
            return None
        return (
            f"manifest declares replicas.desired={desired} but install "
            f"method {install_method!r} only supports single-instance. "
            f"Set replicas.desired: 1 (or omit the replicas block) "
            f"to install via uv, or pick a docker install method."
        )

    def scale(
        self,
        plugin_id: str,
        *,
        desired: int,
        runtime: Optional[RuntimeConfig] = None,
    ) -> LifecycleResult:
        """Add or remove replicas to reach ``desired`` count.

        Docker-only. Scale-up reuses the recorded image_ref + restart
        policy; scale-down stops + removes the excess containers
        (warn-and-proceed: RMQ requeues unacked messages to surviving
        replicas).

        The manifest's ``replicas.min``/``max`` bounds are honored —
        the operator can't escape them via the scale endpoint.
        """
        installer = self._find_installer_for(plugin_id)
        if installer is None:
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                error=f"plugin {plugin_id!r} not installed",
            )
        # Typed capability check — uses the ScalableInstaller Protocol
        # so the contract is explicit rather than hasattr-duck-typed.
        if not isinstance(installer, ScalableInstaller):
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                error=f"scale not supported for install method "
                      f"{installer.method!r}; only docker plugins scale",
            )
        try:
            current, new = installer.scale_to(
                plugin_id, desired=desired,
                runtime=runtime or RuntimeConfig(broker_url="", gpfs_root=""),
            )
        except ValueError as exc:
            return LifecycleResult(
                success=False, plugin_id=plugin_id, error=str(exc),
            )
        return LifecycleResult(
            success=True, plugin_id=plugin_id,
            status=self.status(plugin_id),
            logs=f"scaled {plugin_id} from {current} to {new} replicas",
        )

    def _check_restart_policy_supported(
        self, install_method: str, manifest: PluginArchiveManifest,
    ) -> Optional[str]:
        """Return an error message if the configured supervisor can't
        honor the manifest's restart_policy. ``None`` means proceed.

        The gate is narrow on purpose:
          - Docker handles restart natively via ``--restart`` — always OK.
          - uv + ``no`` policy — always OK; that's the escape hatch.
          - uv + ``systemd-user`` — OK; the unit file does the work.
          - uv + ``popen`` (Windows / macOS dev) — REFUSE; Popen has no
            watchdog and silently dropping the policy would surprise
            operators.
          - uv + ``noop`` (test / no-supervision) — OK; nothing actually
            runs, so the policy is moot. The intent-only flag the noop
            supervisor returns surfaces the manual-launch requirement.
        """
        if install_method != "uv":
            return None
        policy = manifest.lifecycle.restart_policy
        if policy == "no":
            return None
        sup_name = getattr(self._supervisor, "name", "")
        if sup_name in ("systemd-user", "noop"):
            return None
        return (
            f"manifest declares restart_policy={policy!r} but the host's "
            f"plugin supervisor ({sup_name!r}) cannot auto-restart. Either "
            f"set lifecycle.restart_policy: 'no' in the manifest, or run "
            f"on Linux with systemctl --user available."
        )

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
        self,
        manifest: PluginArchiveManifest,
        host: HostInfo,
        *,
        only_method: Optional[str] = None,
    ) -> Optional[Tuple[InstallSpec, Installer]]:
        """Find the first ``(spec, installer)`` pair whose predicates pass.

        ``only_method`` restricts the scan to one method (e.g. ``"uv"``)
        — used when the operator pinned a method via the install endpoint.
        Without it, the first matching method wins (manifest order).
        """
        for spec in manifest.install:
            if only_method and spec.method != only_method:
                continue
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

    def _explain_preferred_unmatched(
        self,
        manifest: PluginArchiveManifest,
        host: HostInfo,
        preferred_method: str,
    ) -> str:
        """Tell the operator *why* their pinned method didn't take.

        Three cases worth distinguishing: the manifest doesn't declare
        that method at all; the host has no installer registered for
        it; or the installer's predicates failed. Each gets a different
        actionable hint."""
        manifest_methods = [s.method for s in manifest.install]
        if preferred_method not in manifest_methods:
            return (
                f"plugin {manifest.plugin_id!r} doesn't declare an install "
                f"method {preferred_method!r}. Available methods in the "
                f"manifest: {manifest_methods or '(none)'}."
            )
        installer = self._installers.get(preferred_method)
        if installer is None:
            return (
                f"this CoreService has no installer registered for "
                f"method {preferred_method!r}. Available installers: "
                f"{sorted(self._installers.keys()) or '(none)'}."
            )
        spec = next(s for s in manifest.install if s.method == preferred_method)
        failures = installer.supports(spec, host)
        joined = "; ".join(failures) if failures else "(unknown)"
        return (
            f"install method {preferred_method!r} not supported by this host: "
            f"{joined}."
        )

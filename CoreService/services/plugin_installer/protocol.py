"""Installer Protocol + dataclasses (P4).

Three kinds of value object travel through the install pipeline:

  - :class:`RuntimeConfig` — what the deployment provides (broker URL,
    GPFS root, extra env). Injected into the plugin at install time.
    Per ``PLUGIN_ARCHIVE_FORMAT.md`` §6, this is NOT in the archive.
  - :class:`InstallResult` — what the manager returns to its caller
    (admin endpoint or REPL). Carries the install's outcome plus
    enough context to debug a failure (logs, error message).
  - :class:`UninstallResult` — symmetric for the uninstall path.

The :class:`Installer` Protocol is the seam different install methods
plug into. Three impls expected:

  - :class:`UvInstaller` (P4) — pure-Python plugins via ``uv``.
  - ``DockerInstaller`` (P5) — image-based plugins.
  - ``SubprocessInstaller`` (v2) — legacy binaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Protocol, runtime_checkable

from magellon_sdk.archive.manifest import InstallSpec, PluginArchiveManifest


@dataclass
class RuntimeConfig:
    """Deployment-supplied values injected into the plugin at install
    time.

    The archive manifest declares what the plugin needs (via
    ``requires: [broker, gpfs]``); this class is what the deployment
    *gives*. Keeping these distinct enforces the secrets-don't-go-in-
    archives rule from the format spec.
    """

    broker_url: str
    """AMQP URL the plugin connects to. ``amqp://user:pass@host:5672/``."""

    gpfs_root: str
    """Absolute path to the shared filesystem (``MAGELLON_HOME_DIR``).
    Plugins read/write image data here per ``DATA_PLANE.md``."""

    extra_env: Dict[str, str] = field(default_factory=dict)
    """Additional environment variables the plugin should see. Useful
    for ad-hoc deployment overrides (e.g. ``LOG_LEVEL=DEBUG``) without
    cycling the install."""


@dataclass
class InstallResult:
    """Outcome of one install attempt."""

    success: bool
    plugin_id: str
    install_method: str
    """Which method the manager picked (``uv`` / ``docker`` / ...).
    On failure with no method picked, this is the empty string."""

    install_dir: Optional[Path] = None
    """Where the plugin was installed. ``None`` on failure (or for
    install methods that don't materialize a directory, e.g. a
    pre-pulled docker image)."""

    pid: Optional[int] = None
    """Plugin process PID, if the installer launched one. ``None``
    means 'install completed but did not spawn'."""

    error: Optional[str] = None
    logs: Optional[str] = None
    """Captured stdout+stderr from the install pipeline. Long but
    invaluable for debugging."""


@dataclass
class UninstallResult:
    success: bool
    plugin_id: str
    error: Optional[str] = None


@runtime_checkable
class Installer(Protocol):
    """One install method. Each impl knows how to unpack, prepare,
    launch, and tear down a plugin via its specific mechanism."""

    method: ClassVar[str]
    """``uv``, ``docker``, ``subprocess``. Must match
    :attr:`InstallSpec.method` strings."""

    def supports(self, install_spec: InstallSpec, host: "HostInfo") -> List[str]:
        """Return a list of failed predicate descriptions, empty if
        the install_spec is supported on this host. The manager walks
        every install entry and picks the first whose support list
        is empty.

        Returning the list (rather than a bool) lets the operator
        see *why* an install method was skipped — debugging "no
        installer matches" is hard without that detail.
        """
        ...

    def install(
        self,
        archive_path: Path,
        manifest: PluginArchiveManifest,
        install_spec: InstallSpec,
        runtime: RuntimeConfig,
    ) -> InstallResult:
        """Install the plugin from a packed ``.mpn`` archive.

        ``install_spec`` is the specific entry from
        ``manifest.install`` the manager picked — installers like
        :class:`DockerInstaller` need it to know whether to use
        ``image:`` or ``dockerfile:``. UvInstaller uses it to honor
        the manifest's ``pyproject:`` path.

        Idempotency: refuse if already installed; the upgrade flow
        (P6) handles version replacement explicitly.
        """
        ...

    def uninstall(
        self, plugin_id: str, *, preserve_as_backup: bool = False,
    ) -> UninstallResult:
        """Remove a previously-installed plugin.

        When ``preserve_as_backup=True`` (used by the upgrade flow
        in :class:`PluginInstallManager`), the install dir is RENAMED
        to ``<plugin_id>.<version>.bak/`` instead of being deleted,
        and any built/pulled image is preserved so a rollback can
        re-run it. The plugin's process / container is still stopped.

        Best-effort: a partial uninstall (e.g. process killed but
        directory still on disk) returns ``success=False`` with the
        residue described in ``error``.
        """
        ...

    def is_installed(self, plugin_id: str) -> bool:
        """Cheap probe — does the manager think this plugin is
        installed under this method? Used at install-time to refuse
        duplicates."""
        ...


# HostInfo lives in predicates.py to keep the module dependency
# direction installer→predicates clean. Re-imported here for the
# Protocol's quoted forward reference.
from services.plugin_installer.predicates import HostInfo  # noqa: E402,F401

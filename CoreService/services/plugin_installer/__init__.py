"""Plugin install pipeline (P4+ in PLUGIN_INSTALL_PLAN.md).

The install controller that consumes ``.mpn`` archives and brings
plugins live on a CoreService host. Composed of:

- :class:`Installer` Protocol — abstract install method (uv / docker /
  subprocess). Each impl knows how to unpack, prepare runtime, and
  start a plugin process for its method.
- :class:`UvInstaller` — first concrete impl (P4). Unpacks under
  ``<plugins_dir>/<plugin_id>/``, builds an isolated venv with
  ``uv``, writes deployment-supplied runtime values, optionally
  launches the plugin process.
- :class:`PluginInstallManager` — orchestrator (P4). Loads + validates
  the manifest, picks the first install method whose ``requires:``
  predicates the host satisfies, dispatches.

DockerInstaller (P5) lands as a sibling impl and registers with the
manager. Uninstall + version upgrade (P6) extend the manager API.
"""
from __future__ import annotations

from services.plugin_installer.docker_installer import DockerInstaller
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import (
    HostInfo,
    detect_host_info,
    evaluate_predicates,
)
from services.plugin_installer.protocol import (
    InstallResult,
    Installer,
    RuntimeConfig,
    UninstallResult,
)
from services.plugin_installer.uv_installer import UvInstaller

__all__ = [
    "DockerInstaller",
    "HostInfo",
    "InstallResult",
    "Installer",
    "PluginInstallManager",
    "RuntimeConfig",
    "UninstallResult",
    "UvInstaller",
    "detect_host_info",
    "evaluate_predicates",
]

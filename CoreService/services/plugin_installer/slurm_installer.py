"""``SlurmInstaller`` — HPC/cluster install method (Wave 6 Phase 26).

Scaffolding only. The Slurm shape is fundamentally different from
docker/uv:

  - Docker + uv plugins are *daemons*: started once, run forever,
    accept tasks off the bus, restart on crash.
  - Slurm plugins are *jobs*: ``sbatch`` submits a job, the job
    runs until its time limit or until cancelled. There's no
    persistent process to ``start`` / ``stop`` / ``pause``.

The BackendLifecycle Protocol assumes the daemon model. To make
Slurm fit cleanly we'd need one of:

  A. **"Install = persistent job"**: sbatch a long-running job at
     install time that drains the bus until cancelled. The Slurm
     job is the equivalent of a Docker container; ``stop`` =
     scancel; ``restart`` = scancel + sbatch. Pause is not
     expressible (no Slurm primitive).

  B. **"Install = job template"**: install just records the
     SBATCH parameters. CoreService submits one job per
     dispatch — Slurm becomes a per-task executor, not a backend.
     This is what ``magellon_sdk.executor.SlurmExecutor`` already
     does (commit 8190e5a) but it sits outside the install
     pipeline.

This file implements **(A)** at the surface level — the Installer
+ Lifecycle Protocols accept the daemon shape — but every method
raises NotImplementedError until an HPC operator has the use case
to drive the actual sbatch wiring. The point is to validate the
abstraction extends, not to ship working Slurm support without
demand.

Wiring it in the factory is intentionally NOT done — that's the
trigger event when an operator says "we have a Slurm cluster and
want to use it."
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from magellon_sdk.archive.manifest import InstallSpec, PluginArchiveManifest

from services.plugin_installer.predicates import HostInfo, evaluate_predicates
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)

logger = logging.getLogger(__name__)


class SlurmInstaller:
    """``Installer`` impl for the ``slurm`` install method.

    Scaffolding: every operation raises NotImplementedError with a
    pointer to the design choice the implementor needs to make
    before wiring real sbatch commands.
    """

    method = "slurm"

    def __init__(
        self, plugins_dir: Path, *, sbatch_command: str = "sbatch",
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.sbatch_command = sbatch_command

    def supports(self, install_spec: InstallSpec, host: HostInfo) -> List[str]:
        if install_spec.method != "slurm":
            return [f"method != slurm (got {install_spec.method!r})"]
        return evaluate_predicates(install_spec.requires, host)

    def install(
        self,
        archive_path: Path,
        manifest: PluginArchiveManifest,
        install_spec: InstallSpec,
        runtime: RuntimeConfig,
    ) -> InstallResult:
        raise NotImplementedError(
            "SlurmInstaller is scaffolding only. Implement one of:\n"
            "  (A) Long-running sbatch job — install kicks off a "
            "persistent bus consumer with a high time limit.\n"
            "  (B) Per-dispatch sbatch — install records the SBATCH "
            "template; CoreService submits per-task.\n"
            "See module docstring for the trade-off."
        )

    def uninstall(
        self, plugin_id: str, *, preserve_as_backup: bool = False,
    ) -> UninstallResult:
        raise NotImplementedError("SlurmInstaller is scaffolding only.")

    def is_installed(self, plugin_id: str) -> bool:
        # No state on disk yet; pretend nothing's installed so the
        # manager's duplicate-check doesn't 500.
        return False


__all__ = ["SlurmInstaller"]

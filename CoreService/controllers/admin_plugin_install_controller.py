"""Admin HTTP surface for the v1 plugin install pipeline (P7).

Five endpoints, all Administrator-gated:

  POST   /admin/plugins/install          — upload .mpn, install
  POST   /admin/plugins/{id}/upgrade     — upload .mpn, replace existing
  DELETE /admin/plugins/{id}             — uninstall
  GET    /admin/plugins/installed        — list installed
  GET    /admin/plugins/{id}             — describe one installed plugin

Install + upgrade accept a multipart file upload only — URL-based
fetch is deferred to P9 when the hub provides authenticated
download URLs.

Status code mapping:

  400 — manifest invalid, archive corrupt, plugin_id mismatch on upgrade
  403 — caller not Administrator (Casbin gate)
  404 — plugin not installed (delete / upgrade / describe)
  409 — already installed (install path)
  500 — unexpected error from the install manager
  201 — install succeeded; new plugin live
  200 — uninstall, upgrade, list, describe succeeded

The legacy ``plugins/controller.py`` endpoint (``POST
/plugins/install/archive``) is the older ``plugin_catalog`` v0
upload path. v1 ``.mpn`` archives flow through this admin surface
instead.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from dependencies.permissions import require_role
from services.plugin_installer.factory import (
    get_install_manager,
    get_runtime_config,
)
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)
from services.plugin_catalog_persistence import (
    PluginCatalogPersistence,
    get_plugin_catalog_persistence,
)

logger = logging.getLogger(__name__)

admin_plugin_install_router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class InstallResponse(BaseModel):
    """Pydantic mirror of :class:`InstallResult` for clean OpenAPI."""

    success: bool
    plugin_id: str
    install_method: str
    install_dir: Optional[str] = None
    pid: Optional[int] = None
    error: Optional[str] = None
    logs: Optional[str] = None

    @classmethod
    def from_result(cls, result: InstallResult) -> "InstallResponse":
        return cls(
            success=result.success,
            plugin_id=result.plugin_id,
            install_method=result.install_method,
            install_dir=str(result.install_dir) if result.install_dir else None,
            pid=result.pid,
            error=result.error,
            logs=result.logs,
        )


class UninstallResponse(BaseModel):
    success: bool
    plugin_id: str
    error: Optional[str] = None

    @classmethod
    def from_result(cls, result: UninstallResult) -> "UninstallResponse":
        return cls(
            success=result.success,
            plugin_id=result.plugin_id,
            error=result.error,
        )


class InstalledPlugin(BaseModel):
    plugin_id: str
    install_method: str


class InstalledListResponse(BaseModel):
    installed: list[InstalledPlugin]


# ---------------------------------------------------------------------------
# Inspect — surface manifest details + per-method host compatibility so
# the React install dialog can show a method dropdown with a sensible
# default before the operator commits to installing.
# ---------------------------------------------------------------------------


class InstallMethodOption(BaseModel):
    """One installable method as the operator should see it in the UI."""

    method: str
    """e.g. ``"uv"``, ``"docker"``."""

    supported: bool
    """True when this CoreService host satisfies the method's predicates
    (registered installer + every requires entry passes). False methods
    can still be selected but the install will fail with the reasons
    below — useful for "I'll fix the docker daemon and retry" flows."""

    failures: list[str] = []
    """Human-readable reasons the method failed predicates (empty when
    ``supported=True``)."""

    notes: Optional[str] = None
    """Free-form description (e.g. ``"image: ghcr.io/.../foo:1.2.3"``)
    so the operator knows what they're picking."""


class InspectResponse(BaseModel):
    plugin_id: str
    name: str
    version: str
    category: str
    sdk_compat: str
    description: Optional[str] = None
    developer: Optional[str] = None
    methods: list[InstallMethodOption]
    """In manifest order — first one the plugin author preferred."""
    default_method: Optional[str] = None
    """Method the install endpoint would auto-pick if no install_method
    were specified. Same first-supported-wins logic the manager uses.
    May be ``None`` when none of the methods are supported on this host
    (the dialog should still let the operator pick something and see
    the per-method failure reasons)."""
    already_installed: bool = False
    """``True`` when an existing install owns this plugin_id — UI can
    nudge the operator toward upgrade instead of install."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _save_upload_to_temp(upload: UploadFile) -> Path:
    """Stream the uploaded file to a temp location so the manager
    can read it as a path. Caller is responsible for unlinking."""
    if not upload.filename:
        raise HTTPException(status_code=400, detail="upload missing filename")
    if not upload.filename.endswith(".mpn"):
        raise HTTPException(
            status_code=400,
            detail=f"upload must be a .mpn archive; got {upload.filename!r}",
        )
    fd, name = tempfile.mkstemp(suffix=".mpn", prefix="upload-")
    try:
        with open(fd, "wb") as out:
            while chunk := await upload.read(1024 * 1024):
                out.write(chunk)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _result_to_http(result: InstallResult, *, success_status: int) -> InstallResponse:
    """Map an install/upgrade result onto the right HTTP status code.

    The error message text drives the mapping — manager-side errors
    are stable strings ("already installed", "not installed",
    "plugin_id"...). Stable enough for switch-on-substring; tested.
    """
    if result.success:
        return InstallResponse.from_result(result)
    err = (result.error or "").lower()
    if "already installed" in err:
        raise HTTPException(status_code=409, detail=result.error)
    if "not installed" in err:
        raise HTTPException(status_code=404, detail=result.error)
    # 422 — archive is well-formed, request is the issue. Order matters:
    # the "not supported / doesn't declare" messages mention "manifest"
    # which would trip the 400 branch below if checked second.
    if (
        "no install method matched" in err
        or "not supported by this host" in err
        or "doesn't declare an install method" in err
        or "no installer registered for method" in err
    ):
        raise HTTPException(status_code=422, detail=result.error)
    if (
        "manifest" in err
        or "plugin_id" in err
        or "checksum" in err
        or "unsafe archive" in err
        or "not newer" in err
    ):
        raise HTTPException(status_code=400, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "install failed")


# ---------------------------------------------------------------------------
# POST /inspect — parse manifest, list install methods, compute default
# ---------------------------------------------------------------------------


@admin_plugin_install_router.post(
    "/inspect",
    response_model=InspectResponse,
    summary="Parse a .mpn archive and report which install methods this host supports",
)
async def inspect_plugin_archive(
    file: UploadFile = File(..., description="The .mpn archive to inspect."),
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
) -> InspectResponse:
    """Read-only counterpart to ``/install``. Stream the upload to a
    temp file, parse the manifest, and return:

      * the plugin's identity (plugin_id, name, version, category)
      * every install method the manifest declares, with this host's
        per-method support verdict and failure reasons
      * the method the install endpoint would auto-pick — useful as
        the dropdown's default selection
      * whether the plugin is already installed (UI hint to upgrade)

    No DB write, no install side-effect. Designed for the React upload
    dialog: user picks a file, we call this, the dropdown populates,
    user (optionally) overrides the default and clicks Install.
    """
    archive_path = await _save_upload_to_temp(file)
    try:
        # Re-use the manager's helpers so the verdict here matches what
        # the install endpoint would actually decide. Importing inside
        # the function keeps the module's import surface unchanged.
        from services.plugin_installer.predicates import collect_required_binaries

        try:
            manifest = manager._load_manifest(archive_path)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"manifest load/validate failed: {exc}",
            )

        required_binaries = collect_required_binaries(
            [s.requires for s in manifest.install]
        )
        host = manager._host_info_provider(  # noqa: SLF001
            probe_binaries=required_binaries,
        )

        methods: list[InstallMethodOption] = []
        for spec in manifest.install:
            installer = manager._installers.get(spec.method)  # noqa: SLF001
            if installer is None:
                failures = [
                    f"no installer registered for method {spec.method!r} on this host"
                ]
                supported = False
            else:
                failures = installer.supports(spec, host)
                supported = not failures
            methods.append(InstallMethodOption(
                method=spec.method,
                supported=supported,
                failures=failures,
                notes=_describe_install_spec(spec),
            ))

        # Default = first supported method in manifest order (mirrors
        # the manager's _pick_installer logic exactly).
        default_method = next(
            (m.method for m in methods if m.supported), None,
        )

        already_installed = manager.is_installed(manifest.plugin_id)

        return InspectResponse(
            plugin_id=manifest.plugin_id,
            name=manifest.name,
            version=manifest.version,
            category=manifest.category,
            sdk_compat=manifest.requires_sdk,
            description=manifest.description or None,
            developer=getattr(manifest, "author", None) or None,
            methods=methods,
            default_method=default_method,
            already_installed=already_installed,
        )
    finally:
        archive_path.unlink(missing_ok=True)


def _describe_install_spec(spec) -> Optional[str]:
    """Tiny one-liner the dropdown can show next to each method so the
    operator knows what's behind the choice (e.g. "image: ghcr.io/...:1.2"
    vs "pyproject: pyproject.toml")."""
    if spec.method == "docker":
        if spec.image:
            return f"image: {spec.image}"
        if spec.dockerfile:
            return f"dockerfile: {spec.dockerfile}"
    if spec.method == "uv" and spec.pyproject:
        return f"pyproject: {spec.pyproject}"
    return None


# ---------------------------------------------------------------------------
# POST /install — upload + install
# ---------------------------------------------------------------------------

@admin_plugin_install_router.post(
    "/install",
    response_model=InstallResponse,
    status_code=201,
    summary="Install a plugin from an uploaded .mpn archive",
)
async def install_plugin(
    file: UploadFile = File(..., description="The .mpn archive to install."),
    install_method: Optional[str] = Form(
        None,
        description=(
            "Optional install method to pin (e.g. 'uv', 'docker'). "
            "When omitted, the manager auto-picks the first method "
            "from the manifest whose host predicates pass. When set, "
            "the manager uses that method exclusively and refuses if "
            "its predicates don't match (no silent fallback)."
        ),
    ),
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
) -> InstallResponse:
    archive_path = await _save_upload_to_temp(file)
    try:
        result = manager.install(
            archive_path, runtime, preferred_method=install_method,
        )
        if result.success:
            try:
                catalog.record_install(archive_path, result)
            except Exception as exc:
                logger.exception(
                    "plugin install succeeded but DB persistence failed; "
                    "rolling back plugin_id=%s",
                    result.plugin_id,
                )
                try:
                    manager.uninstall(result.plugin_id)
                except Exception:
                    logger.exception(
                        "rollback uninstall failed for plugin_id=%s",
                        result.plugin_id,
                    )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "plugin installed but could not be recorded in the "
                        f"database: {exc}"
                    ),
                ) from exc
    finally:
        archive_path.unlink(missing_ok=True)
    return _result_to_http(result, success_status=201)


# ---------------------------------------------------------------------------
# POST /{plugin_id}/upgrade
# ---------------------------------------------------------------------------

@admin_plugin_install_router.post(
    "/{plugin_id}/upgrade",
    response_model=InstallResponse,
    summary="Upgrade an installed plugin from an uploaded .mpn archive",
)
async def upgrade_plugin(
    plugin_id: str,
    file: UploadFile = File(..., description="New version .mpn archive."),
    force_downgrade: bool = Form(
        False,
        description="Allow installing an older version. "
                    "Used for emergency rollback across plugin boundaries.",
    ),
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
) -> InstallResponse:
    archive_path = await _save_upload_to_temp(file)
    try:
        result = manager.upgrade(
            plugin_id, archive_path, runtime, force_downgrade=force_downgrade,
        )
        if result.success:
            try:
                catalog.record_install(archive_path, result)
            except Exception as exc:
                logger.exception(
                    "plugin upgrade succeeded but DB persistence failed: %s",
                    plugin_id,
                )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "plugin upgraded but could not be recorded in the "
                        f"database: {exc}"
                    ),
                ) from exc
    finally:
        archive_path.unlink(missing_ok=True)
    return _result_to_http(result, success_status=200)


# ---------------------------------------------------------------------------
# DELETE /{plugin_id}
# ---------------------------------------------------------------------------

@admin_plugin_install_router.delete(
    "/{plugin_id}",
    response_model=UninstallResponse,
    summary="Uninstall a plugin",
)
def uninstall_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    _: None = Depends(require_role("Administrator")),
) -> UninstallResponse:
    result = manager.uninstall(plugin_id)
    physically_uninstalled = result.success
    if not result.success:
        err = (result.error or "").lower()
        if "not installed" not in err:
            raise HTTPException(status_code=500, detail=result.error)
        # Manager owns no install dir for this plugin. That's the
        # common case for broker-discovered plugins (announce/heartbeat
        # creates a catalog row with install_method='discovered' and
        # no on-disk venv/container) — the operator clicking Uninstall
        # in the UI expects the row to vanish either way. Fall through
        # to the catalog soft-delete; if that also finds nothing, the
        # plugin truly doesn't exist anywhere and we 404.
    try:
        had_row = catalog.record_uninstall(plugin_id)
    except Exception as exc:
        logger.exception("plugin uninstall: DB soft-delete failed: %s", plugin_id)
        if physically_uninstalled:
            raise HTTPException(
                status_code=500,
                detail=(
                    "plugin uninstalled but could not be marked removed in the "
                    f"database: {exc}"
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not physically_uninstalled and not had_row:
        raise HTTPException(status_code=404, detail=result.error)
    return UninstallResponse(
        success=True,
        plugin_id=plugin_id,
        error=None if physically_uninstalled else (
            "plugin had no on-disk install (likely discovered via broker); "
            "removed from catalog only"
        ),
    )


# ---------------------------------------------------------------------------
# GET /installed
# ---------------------------------------------------------------------------

@admin_plugin_install_router.get(
    "/installed",
    response_model=InstalledListResponse,
    summary="List every installed plugin",
)
def list_installed(
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    _: None = Depends(require_role("Administrator")),
) -> InstalledListResponse:
    return InstalledListResponse(
        installed=[
            InstalledPlugin(plugin_id=plugin_id, install_method=method)
            for plugin_id, method in sorted(catalog.list_installed().items())
        ]
    )


# ---------------------------------------------------------------------------
# Lifecycle endpoints — start / stop / restart / status
# ---------------------------------------------------------------------------
#
# The supervisor implements the actual process control (Popen on
# Windows, systemctl on Linux). These endpoints expose it through
# the same admin surface as install/uninstall so the React plugin
# manager UI can offer Run / Stop / Restart buttons next to each
# installed plugin.


@admin_plugin_install_router.post(
    "/{plugin_id}/start",
    summary="Start an installed plugin's process",
)
def start_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    result = manager.start(plugin_id)
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "logs": result.logs,
            "running": manager.is_running(plugin_id),
        }
    err = (result.error or "").lower()
    if "not installed" in err:
        raise HTTPException(status_code=404, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "start failed")


@admin_plugin_install_router.post(
    "/{plugin_id}/stop",
    summary="Stop an installed plugin's process (idempotent)",
)
def stop_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    result = manager.stop(plugin_id)
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "logs": result.logs,
            "running": manager.is_running(plugin_id),
        }
    raise HTTPException(status_code=500, detail=result.error or "stop failed")


@admin_plugin_install_router.post(
    "/{plugin_id}/restart",
    summary="Stop then start the plugin's process",
)
def restart_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    result = manager.restart(plugin_id)
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "logs": result.logs,
            "running": manager.is_running(plugin_id),
        }
    raise HTTPException(status_code=500, detail=result.error or "restart failed")


@admin_plugin_install_router.get(
    "/{plugin_id}/status",
    summary="Process-level status from the supervisor",
)
def plugin_process_status(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    """Lightweight check — does the supervisor see a live PID for
    this plugin? Distinct from ``GET /plugins/{id}/status`` which
    returns the broader Conditions[] (announce-based liveness).
    """
    return {
        "plugin_id": plugin_id,
        "installed": manager.is_installed(plugin_id),
        "running": manager.is_running(plugin_id),
    }


__all__ = ["admin_plugin_install_router"]

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
    if (
        "manifest" in err
        or "plugin_id" in err
        or "checksum" in err
        or "unsafe archive" in err
        or "not newer" in err
    ):
        raise HTTPException(status_code=400, detail=result.error)
    if "no install method matched" in err:
        # 422 Unprocessable Entity — archive is well-formed, but the
        # host doesn't satisfy any of its install methods' predicates.
        raise HTTPException(status_code=422, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "install failed")


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
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
) -> InstallResponse:
    archive_path = await _save_upload_to_temp(file)
    try:
        result = manager.install(archive_path, runtime)
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
    if not result.success:
        err = (result.error or "").lower()
        if "not installed" in err:
            raise HTTPException(status_code=404, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)
    try:
        catalog.record_uninstall(plugin_id)
    except Exception as exc:
        logger.exception("plugin uninstalled but DB soft-delete failed: %s", plugin_id)
        raise HTTPException(
            status_code=500,
            detail=(
                "plugin uninstalled but could not be marked removed in the "
                f"database: {exc}"
            ),
        ) from exc
    return UninstallResponse.from_result(result)


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

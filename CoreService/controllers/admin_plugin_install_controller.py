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

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from magellon_sdk.archive import load_manifest_bytes
from database import get_db
from dependencies.permissions import require_role
from services.plugin_installer.factory import (
    get_install_manager,
    get_runtime_config,
)
from services.plugin_installer.lifecycle import NotSupportedError
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

# ---------------------------------------------------------------------------
# Activity endpoint helpers
# ---------------------------------------------------------------------------
# Category-name → stage code (used to filter ImageJobTask rows for a plugin's
# Activity tab). Mirrors ``_TASK_TYPE_TO_STAGE`` in
# ``services/task_output_processor.py`` but keyed on the human-readable
# category slug we expose through the install manifest. Categories not in
# this map either don't write through ImageJobTask (e.g. fft is in-process
# via the importer) or haven't been integrated yet; we return an empty
# task list rather than error so the tab still renders the queue snapshot.
_CATEGORY_TO_STAGE = {
    "motioncor": 1,
    "ctf": 2,
    "square_detection": 3,
    "hole_detection": 4,
    "topaz_particle_picking": 5,
    "particle_picking": 5,
    "micrograph_denoise": 6,
    "particle_extraction": 7,
    "two_d_classification": 8,
}

# Status-id → human label. Matches the import-controller status enum
# (1=pending, 2=running, 3=processing, 4=completed, 5=failed, 6=cancelled).
_STATUS_LABEL = {
    1: "pending",
    2: "running",
    3: "processing",
    4: "completed",
    5: "failed",
    6: "cancelled",
}


def _queue_names_for_category(category: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Mirror the convention in CoreService/core/helper.py — each
    category exposes ``<slug>_tasks_queue`` for dispatch and
    ``<slug>_out_tasks_queue`` for results. Returns ``(None, None)``
    when the category is missing so the caller falls back to an
    empty queue summary."""
    if not category:
        return None, None
    slug = category.lower().replace(" ", "_").replace("-", "_")
    return f"{slug}_tasks_queue", f"{slug}_out_tasks_queue"


def _fetch_rmq_queue_stats(queue_name: str) -> dict:
    """Proxy a single queue's stats from the RabbitMQ Management API.

    Browsers can't hit the management API directly (it doesn't ship
    CORS headers), and the credentials would be exposed in JS anyway.
    CoreService already has the broker credentials in its settings,
    so the cleanest path is a thin server-side proxy. Returns a
    dict with the fields the Activity tab actually displays; on any
    failure (RMQ down, auth wrong, queue not declared yet) returns
    ``{"available": False, "error": str}`` so the UI can render a
    "not reachable" state rather than blanking the whole tab.
    """
    try:
        from config import app_settings
        rmq = app_settings.rabbitmq_settings
        user = rmq.USER_NAME
        password = rmq.PASSWORD
        host = rmq.HOST_NAME
    except Exception:
        # Settings unavailable in some test paths — fall back to the
        # docker-compose defaults so a dev environment without a YAML
        # still gets useful output instead of a 500.
        user, password, host = "guest", "guest", "localhost"

    # Management port is configurable per deployment but conventionally
    # 5672+10000 = 15672. Read MAGELLON_RMQ_MGMT_PORT to override.
    mgmt_port = int(os.environ.get("MAGELLON_RMQ_MGMT_PORT", "15672"))
    # Default vhost is "/" — URL-encoded as %2F per AMQP convention.
    url = f"http://{host}:{mgmt_port}/api/queues/%2F/{queue_name}"
    try:
        r = httpx.get(url, auth=(user, password), timeout=3.0)
        if r.status_code == 404:
            # Queue not yet declared — common before the first dispatch.
            return {"name": queue_name, "available": True, "depth": 0, "consumers": 0, "exists": False}
        r.raise_for_status()
        data = r.json()
        return {
            "name": queue_name,
            "available": True,
            "exists": True,
            "depth": int(data.get("messages", 0) or 0),
            "depth_ready": int(data.get("messages_ready", 0) or 0),
            "depth_unacked": int(data.get("messages_unacknowledged", 0) or 0),
            "consumers": int(data.get("consumers", 0) or 0),
            "memory_bytes": int(data.get("memory", 0) or 0),
            "state": data.get("state"),
        }
    except Exception as exc:  # noqa: BLE001 — surface the actual failure
        return {"name": queue_name, "available": False, "error": str(exc)[:160]}

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


def _persist_to_packages_dir(archive_path: Path) -> None:
    """Side-record an installed/upgrading archive under
    ``PLUGIN_PACKAGES_DIR`` so it surfaces in the React "Downloaded"
    tab. Best-effort: a write failure here logs but never fails the
    install — physical install correctness wins over catalog UX.

    Why save here instead of letting the operator upload twice (once
    to ``/plugins/catalog`` for visibility + once to ``/admin/plugins/install``
    for the actual install): the v1 modern install path was bypassing
    the filesystem catalog entirely, so hub installs and dialog uploads
    landed nowhere visible. The catalog is the right place for both —
    it lets the operator re-install / re-share / inspect the archive
    after install completes, even after uninstall.

    Uses :class:`magellon_sdk.archive.PluginArchiveManifest` to parse
    so the catalog's per-version naming convention
    (``{plugin_id}-{version}.mpn``) stays consistent regardless of what
    the upload's original filename was.
    """
    try:
        from core.plugin_catalog import get_catalog
        archive_bytes = archive_path.read_bytes()
        # Re-parse the manifest from the archive itself rather than
        # trusting the install manager's view; same defensive parse the
        # manager does. Catalog only stores well-formed archives.
        with __import__("zipfile").ZipFile(archive_path) as z:
            for name in ("manifest.yaml", "plugin.yaml"):
                try:
                    raw = z.read(name)
                    break
                except KeyError:
                    continue
            else:
                logger.warning(
                    "catalog persist skipped — neither manifest.yaml nor "
                    "plugin.yaml in %s",
                    archive_path,
                )
                return
        manifest = load_manifest_bytes(raw)
        get_catalog().upload(archive_bytes=archive_bytes, manifest=manifest)
    except Exception:  # noqa: BLE001 — catalog is non-load-bearing for install
        logger.warning(
            "failed to mirror install archive into PLUGIN_PACKAGES_DIR; "
            "the plugin still installs correctly but won't appear in the "
            "Downloaded tab.",
            exc_info=True,
        )


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
    # Mirror into PLUGIN_PACKAGES_DIR before install so the Downloaded
    # tab reflects what was uploaded even if install fails partway.
    _persist_to_packages_dir(archive_path)
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
    _persist_to_packages_dir(archive_path)
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
# GET /{plugin_id}/upgrades — list hub-published versions newer than installed
# ---------------------------------------------------------------------------


class UpgradeCandidate(BaseModel):
    version: str
    requires_sdk: Optional[str] = None
    archive_url: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    published_at: Optional[str] = None


class UpgradeListResponse(BaseModel):
    plugin_id: str
    current_version: Optional[str] = None
    candidates: list[UpgradeCandidate]
    """Hub-published versions for this plugin. Includes the currently
    installed version (if any) so the UI can render it for reference;
    the React dialog filters/sorts client-side."""


def _read_installed_version_for(
    manager: PluginInstallManager, plugin_id: str,
) -> Optional[str]:
    """Read the on-disk manifest's version. ``None`` when uninstalled
    or the manifest can't be parsed."""
    installer = manager._find_installer_for(plugin_id)  # noqa: SLF001
    if installer is None:
        return None
    return manager._read_installed_version(installer, plugin_id)  # noqa: SLF001


@admin_plugin_install_router.get(
    "/{plugin_id}/upgrades",
    response_model=UpgradeListResponse,
    summary="List hub-published versions for a plugin",
)
def list_plugin_upgrades(
    plugin_id: str,
    hub_url: Optional[str] = Query(
        None,
        description="Override the hub base URL. Defaults to MAGELLON_HUB_URL "
                    "env or https://magellon.org.",
    ),
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
) -> UpgradeListResponse:
    """Query the hub for published versions of this plugin.

    Returns every version the hub knows about (including ones older
    than the installed one — the React dialog filters client-side and
    handles the rollback case via force_downgrade).
    """
    hub_base = (hub_url or _default_hub_url()).rstrip("/")
    timeout = float(os.environ.get("MAGELLON_HUB_TIMEOUT_SECONDS", "30"))

    try:
        hub_payload = _fetch_hub_manifest(hub_base, plugin_id, timeout=timeout)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"hub unreachable: {exc}")

    candidates: list[UpgradeCandidate] = []
    for entry in hub_payload.get("versions") or []:
        archive = entry.get("archive") or {}
        archive_url = archive.get("url") or archive.get("filename")
        # Expand hub-relative URLs same as the install path.
        if archive_url and not (
            archive_url.startswith("http://") or archive_url.startswith("https://")
        ):
            archive_url = hub_base + "/" + archive_url.lstrip("/")
        candidates.append(UpgradeCandidate(
            version=entry.get("version", ""),
            requires_sdk=entry.get("requires_sdk"),
            archive_url=archive_url,
            sha256=archive.get("sha256"),
            size_bytes=archive.get("size_bytes"),
            published_at=entry.get("published_at"),
        ))

    return UpgradeListResponse(
        plugin_id=plugin_id,
        current_version=_read_installed_version_for(manager, plugin_id),
        candidates=candidates,
    )


# ---------------------------------------------------------------------------
# POST /{plugin_id}/upgrade-from-hub — JSON upgrade with hub-fetched archive
# ---------------------------------------------------------------------------


class UpgradeFromHubRequest(BaseModel):
    """JSON-body counterpart to ``POST /{plugin_id}/upgrade`` for the
    React UpgradeDialog (Phase 9). Same shape as
    :class:`InstallFromHubRequest` plus the ``force_downgrade`` flag
    the existing multipart upgrade endpoint exposes."""

    version: str = Field(..., description="Target version.")
    force_downgrade: bool = Field(
        False,
        description="Permit installing a version older than the current "
                    "one. Used for emergency rollback.",
    )
    hub_url: Optional[str] = Field(
        None, description="Override the hub base URL.",
    )


@admin_plugin_install_router.post(
    "/{plugin_id}/upgrade-from-hub",
    response_model=InstallResponse,
    summary="Upgrade an installed plugin to a hub-published version",
)
def upgrade_from_hub(
    plugin_id: str,
    body: UpgradeFromHubRequest,
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
) -> InstallResponse:
    """Server-side counterpart of the upload-based upgrade.

    Fetches the .mpn from the hub, verifies sha256 (502 on mismatch —
    same threat model as install-from-hub), then delegates to
    :meth:`PluginInstallManager.upgrade` with the canonical rollback
    behaviour (versioned .bak preserved on failure).

    Warn-and-proceed: callers should query ``GET /admin/plugins/{id}``
    or the job-state surface first to surface in-flight task counts to
    the operator. RMQ requeues unacked messages from the killed
    container so in-flight tasks re-run on the new version — no data
    loss but possibly duplicate work.
    """
    hub_base = (body.hub_url or _default_hub_url()).rstrip("/")
    timeout = float(os.environ.get("MAGELLON_HUB_TIMEOUT_SECONDS", "30"))

    hub_manifest = _fetch_hub_manifest(hub_base, plugin_id, timeout=timeout)
    archive_path_or_url, expected_sha256 = _resolve_hub_archive(
        hub_manifest, plugin_id, body.version,
    )
    if archive_path_or_url.startswith("http://") or archive_path_or_url.startswith("https://"):
        absolute_url = archive_path_or_url
    else:
        absolute_url = hub_base + "/" + archive_path_or_url.lstrip("/")

    archive_path = _download_archive(
        absolute_url, expected_sha256, timeout=timeout,
    )
    _persist_to_packages_dir(archive_path)
    try:
        result = manager.upgrade(
            plugin_id, archive_path, runtime,
            force_downgrade=body.force_downgrade,
        )
        if result.success:
            try:
                catalog.record_install(archive_path, result)
            except Exception as exc:
                logger.exception(
                    "upgrade-from-hub succeeded but DB persistence failed: %s",
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
# POST /install-from-hub — fetch a published .mpn from the hub catalog
# ---------------------------------------------------------------------------


class InstallFromHubRequest(BaseModel):
    """Request body for ``POST /admin/plugins/install-from-hub``.

    The hub publishes ``/v1/plugins/{plugin_id}.json`` with the
    archive URL + sha256. CoreService fetches both, verifies the
    digest, then delegates to the existing :meth:`install` flow.
    """

    plugin_id: str = Field(..., description="The plugin's manifest plugin_id (e.g. 'fft').")
    version: str = Field(..., description="Exact version string (e.g. '1.1.0').")
    install_method: Optional[str] = Field(
        None,
        description="Optional install method pin ('uv' / 'docker'). Same "
                    "semantics as the /install endpoint — omit to auto-pick.",
    )
    hub_url: Optional[str] = Field(
        None,
        description="Override the configured hub base URL (e.g. for testing "
                    "against a mirror). Defaults to MAGELLON_HUB_URL env or "
                    "https://magellon.org.",
    )


def _default_hub_url() -> str:
    """Resolve the hub base URL. Env override > prod default."""
    return os.environ.get("MAGELLON_HUB_URL", "https://magellon.org").rstrip("/")


def _fetch_hub_manifest(hub_url: str, plugin_id: str, *, timeout: float) -> dict:
    """``GET <hub>/v1/plugins/{plugin_id}.json`` → parsed JSON."""
    url = f"{hub_url}/v1/plugins/{plugin_id}.json"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"hub unreachable: {exc}")
    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"hub has no plugin {plugin_id!r} at {url}",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"hub returned {resp.status_code}: {resp.text[:200]}",
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"hub returned non-JSON: {exc}",
        )


def _resolve_hub_archive(
    hub_manifest: dict, plugin_id: str, version: str,
) -> tuple[str, str]:
    """Locate the requested version in the hub's per-plugin JSON.

    Returns ``(archive_url, sha256)`` — both relative to the hub base
    are normalized to absolute by the caller.

    Accepts two hub shapes:

      Nested (MAGELLON_HUB_SPEC.md target shape):
        {"versions": [{"version": "1.1.0",
                       "archive": {"url": "...", "sha256": "..."}, ...}]}

      Flat (what demo.magellon.org actually serves today via the
      Astro content collection):
        {"versions": [{"version": "1.1.0", "url": "...",
                       "sha256": "..."}]}

    Either layout works — the version entry just has to carry a URL
    and a sha256 somewhere reachable.
    """
    versions = hub_manifest.get("versions") or []
    for entry in versions:
        if entry.get("version") != version:
            continue
        archive = entry.get("archive") or {}
        # Prefer nested fields, fall back to flat-at-version-level.
        url = archive.get("url") or archive.get("filename") or entry.get("url")
        sha256 = archive.get("sha256") or entry.get("sha256")
        if not url or not sha256:
            raise HTTPException(
                status_code=502,
                detail=f"hub entry for {plugin_id}@{version} missing "
                       f"url or sha256 (checked archive.url, archive.filename, "
                       f"and top-level url/sha256)",
            )
        return url, sha256
    available = [v.get("version") for v in versions if v.get("version")]
    raise HTTPException(
        status_code=404,
        detail=f"hub has plugin {plugin_id!r} but not version {version!r}. "
               f"Available: {available}",
    )


def _download_archive(
    archive_url: str, expected_sha256: str, *, timeout: float,
) -> Path:
    """Stream the archive to a temp file, verify sha256 before returning.

    Verifying the digest at the install boundary is the only thing
    standing between us and a malicious hub serving a different archive
    under a known-good plugin_id+version. Refuse on mismatch.
    """
    try:
        resp = httpx.get(archive_url, timeout=timeout, follow_redirects=True)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail=f"failed to fetch archive: {exc}",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"archive fetch returned {resp.status_code} from {archive_url}",
        )

    digest = hashlib.sha256(resp.content).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise HTTPException(
            status_code=502,
            detail=f"archive sha256 mismatch: hub said {expected_sha256}, "
                   f"got {digest}. Refusing to install.",
        )

    fd, name = tempfile.mkstemp(suffix=".mpn", prefix="hub-")
    try:
        with open(fd, "wb") as out:
            out.write(resp.content)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


@admin_plugin_install_router.post(
    "/install-from-hub",
    response_model=InstallResponse,
    status_code=201,
    summary="Install a plugin by fetching its .mpn from the published hub catalog",
)
def install_from_hub(
    body: InstallFromHubRequest,
    manager: PluginInstallManager = Depends(get_install_manager),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
) -> InstallResponse:
    """One-click install from the public hub.

    Same install pipeline as the manual upload path — the only
    difference is *where the .mpn comes from*: instead of a multipart
    upload from the operator's browser, we fetch it from the hub
    (default ``magellon.org``), verify the sha256 against the hub's
    catalog, and hand the resulting temp file to the existing
    :meth:`PluginInstallManager.install`.
    """
    hub_url = (body.hub_url or _default_hub_url()).rstrip("/")
    hub_timeout = float(os.environ.get("MAGELLON_HUB_TIMEOUT_SECONDS", "30"))

    hub_manifest = _fetch_hub_manifest(
        hub_url, body.plugin_id, timeout=hub_timeout,
    )
    archive_path_or_url, expected_sha256 = _resolve_hub_archive(
        hub_manifest, body.plugin_id, body.version,
    )

    # The hub publishes archive URLs either absolute (``https://...``)
    # or hub-relative (``/assets/plugins/...``) — accept either, expand
    # relative against the hub base.
    if archive_path_or_url.startswith("http://") or archive_path_or_url.startswith("https://"):
        absolute_url = archive_path_or_url
    else:
        absolute_url = hub_url + "/" + archive_path_or_url.lstrip("/")

    archive_path = _download_archive(
        absolute_url, expected_sha256, timeout=hub_timeout,
    )
    _persist_to_packages_dir(archive_path)
    try:
        result = manager.install(
            archive_path, runtime, preferred_method=body.install_method,
        )
        if result.success:
            try:
                catalog.record_install(archive_path, result)
            except Exception as exc:
                logger.exception(
                    "plugin install (from hub) succeeded but DB persistence "
                    "failed; rolling back plugin_id=%s",
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


@admin_plugin_install_router.post(
    "/{plugin_id}/pause",
    summary="Pause an installed plugin's container (docker-only)",
)
def pause_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    """Pause via ``docker pause`` — cheap, instantaneous, memory stays
    resident. uv-installed plugins return 409 with an actionable
    message; operators should use Stop instead."""
    try:
        result = manager.pause(plugin_id)
    except NotSupportedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "logs": result.logs,
            "status": result.status.value,
        }
    err = (result.error or "").lower()
    if "not installed" in err:
        raise HTTPException(status_code=404, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "pause failed")


@admin_plugin_install_router.post(
    "/{plugin_id}/unpause",
    summary="Resume a paused plugin's container (docker-only)",
)
def unpause_plugin(
    plugin_id: str,
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    try:
        result = manager.unpause(plugin_id)
    except NotSupportedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "logs": result.logs,
            "status": result.status.value,
        }
    err = (result.error or "").lower()
    if "not installed" in err:
        raise HTTPException(status_code=404, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "unpause failed")


class ScaleRequest(BaseModel):
    """Body for ``POST /admin/plugins/{plugin_id}/scale``."""

    desired: int = Field(
        ..., ge=1, le=128,
        description="Target replica count. Validated against the manifest's "
                    "replicas.min/max at the manager. Out-of-bounds returns 422.",
    )


@admin_plugin_install_router.post(
    "/{plugin_id}/scale",
    summary="Add or remove replicas (docker-only)",
)
def scale_plugin(
    plugin_id: str,
    body: ScaleRequest,
    manager: PluginInstallManager = Depends(get_install_manager),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    _: None = Depends(require_role("Administrator")),
):
    """Scale the plugin's replica set to ``body.desired``.

    Docker-only — uv plugins return 422. Scale-down is warn-and-proceed
    (RMQ requeues unacked tasks to surviving replicas). Manifest's
    ``replicas.min/max`` bounds are enforced; out-of-bounds returns
    422 with the bounds in the detail.
    """
    if not manager.is_installed(plugin_id):
        raise HTTPException(
            status_code=404, detail=f"plugin {plugin_id!r} not installed",
        )
    result = manager.scale(plugin_id, desired=body.desired, runtime=runtime)
    if result.success:
        return {
            "success": True,
            "plugin_id": result.plugin_id,
            "desired": body.desired,
            "status": result.status.value,
            "logs": result.logs,
        }
    err = (result.error or "").lower()
    if "docker-only" in err or "uv" in err:
        raise HTTPException(status_code=422, detail=result.error)
    if "outside manifest bounds" in err:
        raise HTTPException(status_code=422, detail=result.error)
    if "not installed" in err:
        raise HTTPException(status_code=404, detail=result.error)
    raise HTTPException(status_code=500, detail=result.error or "scale failed")


@admin_plugin_install_router.get(
    "/{plugin_id}/logs",
    summary="Tail the plugin's log source",
)
def plugin_logs(
    plugin_id: str,
    tail: int = Query(200, ge=1, le=10000, description="lines from the end"),
    manager: PluginInstallManager = Depends(get_install_manager),
    _: None = Depends(require_role("Administrator")),
):
    """Return the last ``tail`` lines from the plugin's log source.

    Docker installs shell ``docker logs --tail N <container>``;
    uv installs read ``<install_dir>/app.log`` (Popen) or
    ``journalctl --user`` (systemd-user). Empty body when the plugin
    isn't installed or the backend can't produce logs (NoOp).

    Live streaming uses the Socket.IO ``plugin_log`` channel — clients
    emit ``join_plugin_room`` with ``{"plugin_id": "..."}`` and receive
    one line per ``plugin_log`` event.
    """
    if not manager.is_installed(plugin_id):
        raise HTTPException(
            status_code=404, detail=f"plugin {plugin_id!r} not installed",
        )
    return {
        "plugin_id": plugin_id,
        "tail": tail,
        "lines": manager.logs(plugin_id, tail=tail).splitlines(),
    }


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

    ``status`` returns the typed lifecycle state (running / stopped /
    paused / unknown); ``supports_pause`` lets the React UI grey out
    the Pause button on uv plugins so operators don't try-and-409.
    """
    return {
        "plugin_id": plugin_id,
        "installed": manager.is_installed(plugin_id),
        "running": manager.is_running(plugin_id),
        "status": manager.status(plugin_id).value,
        "supports_pause": manager.supports_pause(plugin_id),
    }


@admin_plugin_install_router.get(
    "/{plugin_id}/activity",
    summary="Aggregate runtime activity for the plugin's tab",
)
def plugin_activity(
    plugin_id: str,
    limit: int = Query(50, ge=1, le=500, description="recent tasks to return"),
    manager: PluginInstallManager = Depends(get_install_manager),
    db = Depends(get_db),  # noqa: B008 — FastAPI dependency injection
    _: None = Depends(require_role("Administrator")),
):
    """Back the per-plugin Activity tab.

    Returns three things in one shot so the React tab doesn't fan out
    into three queries on every poll:

      - ``queues``: live depth + consumer count from the RabbitMQ
        management API, for the plugin's ``<category>_tasks_queue``
        and ``<category>_out_tasks_queue``. Proxied server-side
        because the management API doesn't ship CORS headers and the
        credentials live in CoreService's settings.
      - ``recent_tasks``: last N ``image_job_task`` rows where
        ``plugin_id`` matches OR ``stage`` matches this category's
        stage code. Carries enough columns (status, image_name,
        plugin_version, timestamps) for a quick-scan table.
      - ``category``: echo of what the rest of the response is
        scoped to, so the caller can stamp the tab header.

    Polled by the UI every 3–5s; the RMQ proxy has an explicit
    3-second timeout so a broker hiccup doesn't stall the tab.
    """
    if not manager.is_installed(plugin_id):
        raise HTTPException(
            status_code=404, detail=f"plugin {plugin_id!r} not installed",
        )

    # Category lives on the plugin catalog row (Plugin.category), seeded
    # by the install pipeline from the manifest. It's the join key
    # between queue names + the stage filter on ImageJobTask.
    from models.sqlalchemy_models import ImageJobTask, Plugin
    from sqlalchemy import or_

    plugin_row = (
        db.query(Plugin)
        .filter(Plugin.manifest_plugin_id == plugin_id)
        .first()
    )
    category = plugin_row.category if plugin_row else None

    in_queue_name, out_queue_name = _queue_names_for_category(category)
    queues = []
    if in_queue_name:
        queues.append({**_fetch_rmq_queue_stats(in_queue_name), "direction": "in"})
    if out_queue_name:
        queues.append({**_fetch_rmq_queue_stats(out_queue_name), "direction": "out"})

    # ImageJobTask query: rows scoped to this plugin. Two predicates
    # OR'd together — plugin_id (provenance, set on completion) and
    # stage (matches the category, also set on completion). Either
    # is sufficient evidence the row belongs to this plugin's history.
    stage_code = _CATEGORY_TO_STAGE.get((category or "").lower())
    recent_tasks: list[dict] = []
    try:
        preds = [ImageJobTask.plugin_id == plugin_id]
        if stage_code is not None:
            preds.append(ImageJobTask.stage == stage_code)
        rows = (
            db.query(ImageJobTask)
            .filter(or_(*preds))
            .order_by(ImageJobTask.oid.desc())
            .limit(limit)
            .all()
        )
        for row in rows:
            recent_tasks.append({
                "oid": str(row.oid),
                "job_id": str(row.job_id) if row.job_id else None,
                "image_id": str(row.image_id) if row.image_id else None,
                "image_name": row.image_name,
                "status_id": row.status_id,
                "status": _STATUS_LABEL.get(row.status_id or 0, "unknown"),
                "stage": row.stage,
                "plugin_id": row.plugin_id,
                "plugin_version": row.plugin_version,
                "subject_kind": row.subject_kind,
                "subject_id": str(row.subject_id) if row.subject_id else None,
            })
    except Exception as exc:  # noqa: BLE001 — never break the tab on a DB hiccup
        logger.warning("activity: db query failed: %s", exc)

    return {
        "plugin_id": plugin_id,
        "category": category,
        "queues": queues,
        "recent_tasks": recent_tasks,
    }


__all__ = ["admin_plugin_install_router"]

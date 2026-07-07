"""Install / catalog / installed-container routes for the plugins router.

Shared install mechanics (archive parsing, SDK-compat, docker-run from
manifest) live in :mod:`plugins.install_service`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from core.installed_plugins import get_installed_registry
from core.plugin_catalog import get_catalog
from core.plugin_docker_runner import (
    VolumeMount,
    get_runner as get_docker_runner,
)
from core.plugin_liveness_registry import get_registry as get_liveness_registry

from plugins.install_service import (
    _enforce_sdk_compat,
    _ensure_docker,
    _install_from_manifest,
    _parse_archive_bytes,
)
from plugins.schemas import (
    _CatalogInstallResponse,
    _InstallPluginRequest,
)

lifecycle_router = APIRouter()


# ---------------------------------------------------------------------------
# Install flow — spawn a plugin container from a Docker image ref (H2)
# ---------------------------------------------------------------------------
#
# Security note: this endpoint launches arbitrary Docker images with the
# CoreService user's Docker privileges. In effect, anyone who can POST
# here can run code on the host. Gate behind an admin-only auth scope
# before exposing /plugins/install beyond localhost. H2 ships the
# mechanism; auth is a cross-cutting concern tracked separately.
#
# Scope clarification: H2 owns the container lifecycle. The operator is
# responsible for the image pointing at the right RMQ and declaring the
# right task_queue — CoreService does not inject config. A follow-up
# phase (plugin images reading RMQ from env with yaml fallback) can
# make "install arbitrary image and it just works" possible; today we
# assume the image was built for this deployment.

@lifecycle_router.post("/install", summary="Install a plugin from a Docker image")
async def install_plugin(request: _InstallPluginRequest) -> Dict[str, Any]:
    """Spawn a plugin container in detached mode.

    The container will announce itself on ``magellon.plugins.announce.*``
    if it's a Magellon plugin image built for this deployment. That
    announcement flows into the liveness registry (same path the
    fixed-set plugins use); the GET /plugins/ page picks it up on the
    next refresh with ``kind=broker``.

    If the image is misconfigured (wrong RMQ host, wrong credentials,
    not actually a plugin), ``docker run`` itself succeeds but the
    plugin never announces. The installed-plugins entry stays
    ``running`` with no liveness match — the UI surfaces this as
    "installed but not announcing" so the operator can diagnose
    without CoreService pretending to know more than it does.
    """
    _ensure_docker()
    runner = get_docker_runner()
    volumes = [
        VolumeMount(v.host_path, v.container_path, v.read_only) for v in request.volumes
    ]
    entry = runner.run_image(
        image_ref=request.image_ref,
        env=request.env,
        volumes=volumes,
        network=request.network,
    )
    if entry.state == "failed":
        # Still record the entry so the operator can read the error
        # message from GET /installed; running it through the registry
        # keeps one consistent "where is my install" story.
        get_installed_registry().add(entry)
        raise HTTPException(
            status_code=502,
            detail=f"docker run failed: {entry.error or 'unknown error'}",
        )
    get_installed_registry().add(entry)
    return entry.to_dict()


@lifecycle_router.post(
    "/install/archive",
    summary="Install a plugin from a .mpn archive upload",
)
async def install_plugin_archive(
    archive: UploadFile = File(..., description="A .mpn zip archive."),
) -> Dict[str, Any]:
    """Accept a ``.mpn`` archive, validate its manifest, spawn
    the container using manifest defaults.

    The archive is what ``magellon-sdk plugin pack`` produces: a zip
    with a top-level ``plugin.yaml`` (see :mod:`magellon_sdk.archive`).
    """
    try:
        raw = await archive.read()
    finally:
        await archive.close()

    manifest = _parse_archive_bytes(raw)
    _enforce_sdk_compat(manifest)
    return _install_from_manifest(manifest)


# ---------------------------------------------------------------------------
# Plugin catalog (H3b) — filesystem-backed store for uploaded archives
# ---------------------------------------------------------------------------
#
# Upload is immediate-publish — no human review gate. See
# core/plugin_catalog.py top-of-module note for where that lives when
# we add it. Trust model: same as /install. Gate behind admin auth
# before public exposure.


@lifecycle_router.get("/catalog", summary="Browse the plugin catalog")
async def browse_catalog(
    search: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Return catalog entries with optional substring + category filter.

    ``categories`` is included so the UI can render a filter bar showing
    only categories that actually have entries — avoids dead chips.
    """
    cat = get_catalog()
    entries = [e.to_dict() for e in cat.search(query=search, category=category)]
    return {"entries": entries, "categories": cat.categories()}


@lifecycle_router.post("/catalog", summary="Upload a plugin archive to the catalog")
async def upload_catalog_entry(
    archive: UploadFile = File(..., description="A .mpn zip archive."),
) -> Dict[str, Any]:
    """Publish a ``.mpn`` archive to the catalog.

    Validates the manifest up front; SDK-compat mismatch is a warning
    here, not a hard fail — the catalog may host archives targeting
    future SDK versions, and the install endpoint enforces compat at
    install time.
    """
    try:
        raw = await archive.read()
    finally:
        await archive.close()

    manifest = _parse_archive_bytes(raw)
    # Do NOT _enforce_sdk_compat here — an archive incompatible with
    # today's CoreService may still be useful to catalog for a future
    # upgrade. Compat is checked at install time instead.
    entry = get_catalog().upload(archive_bytes=raw, manifest=manifest)
    return {"catalog_id": entry.catalog_id, **entry.to_dict()}


@lifecycle_router.delete(
    "/catalog/{catalog_id}",
    summary="Remove an entry from the catalog",
)
async def delete_catalog_entry(catalog_id: str) -> Dict[str, Any]:
    entry = get_catalog().remove(catalog_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"catalog entry {catalog_id} not found")
    return entry.to_dict()


@lifecycle_router.post(
    "/catalog/{catalog_id}/install",
    summary="Install a plugin from a catalog entry",
)
async def install_catalog_entry(catalog_id: str) -> _CatalogInstallResponse:
    """Re-use the upload-path install logic against the stored archive.

    Compat is enforced here (not at upload time) so catalog browsers
    see the entry even when it targets a future SDK — they just can't
    install it until CoreService upgrades.
    """
    entry = get_catalog().get(catalog_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"catalog entry {catalog_id} not found")
    _enforce_sdk_compat(entry.manifest)
    install_response = _install_from_manifest(entry.manifest)
    return _CatalogInstallResponse(install=install_response, catalog_id=catalog_id)


@lifecycle_router.get("/installed", summary="List installed plugin containers")
async def list_installed() -> Dict[str, Any]:
    """Return current installs with Docker-refreshed state.

    Joins each install_id against the liveness registry so the UI can
    distinguish "container is running and announcing" (healthy) from
    "container is running but not announcing" (config issue) and
    "container stopped/crashed" (Docker-level failure).
    """
    _ensure_docker()
    runner = get_docker_runner()
    live_plugin_ids = {
        e.plugin_id for e in get_liveness_registry().list_live()
    }

    rows: List[Dict[str, Any]] = []
    for entry in get_installed_registry().list():
        docker_state = runner.inspect_state(entry)
        if docker_state is not None:
            entry.state = docker_state
        row = entry.to_dict()
        # Best-effort liveness hint: if ANY live plugin was recorded
        # since this container started, mark it announcing. We can't
        # key on container_id (liveness doesn't know Docker IDs), so
        # this is a coarse "is anyone new talking?" signal. Future
        # work: have plugins stamp their container_id on Announce.
        row["announcing_on_bus"] = bool(live_plugin_ids)
        rows.append(row)
    return {"installed": rows}


@lifecycle_router.post("/installed/{install_id}/stop", summary="Stop an installed container")
async def stop_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().get(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().stop(entry)
    return entry.to_dict()


@lifecycle_router.delete("/installed/{install_id}", summary="Remove an installed container")
async def remove_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().remove(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().remove(entry)
    return entry.to_dict()

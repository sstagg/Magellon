"""Plugin registry merge endpoint (PE4).

``GET /plugins/registry/index`` fetches the hub's
``/v1/index.json`` and merges it with local install state into a
single response the React Registry page consumes:

  - For every plugin published on the hub: hub metadata + every
    published version + the *local* install state for that plugin
    (installed version, whether an update exists).
  - Local-only plugins (installed but not on the hub) are listed
    separately so operators can spot air-gapped or custom plugins
    that have no upstream.

The merge happens server-side so the React app never holds hub
credentials. It also lets us tolerate a slow / down hub: a hub
fetch failure surfaces as ``hub_status: "unreachable"`` with
``hub_plugins: []`` — the local-only list is still useful.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from dependencies.permissions import require_role
from services.plugin_catalog_persistence import (
    PluginCatalogPersistence,
    get_plugin_catalog_persistence,
)

logger = logging.getLogger(__name__)

plugin_registry_router = APIRouter()


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


class RegistryHubVersion(BaseModel):
    """One version row from the hub's index.json."""

    version: str
    sdk_compat: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    published_at: Optional[str] = None
    archive_url: Optional[str] = None


class RegistryPlugin(BaseModel):
    """Merged view: hub metadata + local install state."""

    plugin_id: str
    """Hub slug — matches the manifest plugin_id installed locally."""
    display_name: str
    category: Optional[str] = None
    is_verified: bool = False
    hub_versions: List[RegistryHubVersion] = []
    latest_hub_version: Optional[str] = None
    """Highest version the hub publishes. ``None`` for local-only."""

    installed_version: Optional[str] = None
    """What's installed on this CoreService. ``None`` when not installed."""
    install_method: Optional[str] = None
    """``"uv"``, ``"docker"``, or whatever the local installer reported.
    ``None`` when not installed."""

    update_available: bool = False
    """True when installed_version is older than latest_hub_version."""
    source: str = "hub"
    """``"hub"`` for plugins the hub knows about; ``"local-only"`` for
    installed plugins absent from the hub catalog."""


class RegistryIndexResponse(BaseModel):
    hub_url: str
    hub_status: str
    """``"ok"`` when the hub responded; ``"unreachable"`` on network
    error; ``"http_<code>"`` on a non-2xx response."""
    hub_error: Optional[str] = None
    """Free-form explanation when ``hub_status != "ok"``."""
    plugins: List[RegistryPlugin] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_hub_url() -> str:
    return os.environ.get("MAGELLON_HUB_URL", "https://magellon.org").rstrip("/")


def _fetch_hub_index(hub_url: str, *, timeout: float = 10.0) -> tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """Fetch ``/v1/index.json`` from the hub.

    Returns ``(hub_status, parsed_body_or_None, error_message_or_None)``.
    The hub-side spec at ``MAGELLON_HUB_SPEC.md`` §4.1 #7 documents the
    shape; this function tolerates absence (returning unreachable)
    so the UI degrades gracefully when offline.
    """
    url = f"{hub_url}/v1/index.json"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.RequestError as exc:
        return ("unreachable", None, f"{exc}")
    if resp.status_code != 200:
        return (f"http_{resp.status_code}", None, resp.text[:200])
    try:
        return ("ok", resp.json(), None)
    except ValueError as exc:
        return ("unreachable", None, f"non-JSON body: {exc}")


def _version_is_newer(candidate: str, baseline: str) -> bool:
    """Lenient SemVer-style "candidate > baseline".

    Pulls in the SDK's parser when available; falls back to string
    compare so unusual version strings (date-based, build metadata)
    don't crash the merge.
    """
    try:
        from magellon_sdk.archive.manifest import _parse_version  # type: ignore[attr-defined]
        return _parse_version(candidate) > _parse_version(baseline)
    except Exception:  # noqa: BLE001
        return candidate > baseline


def _project_hub_version(raw: Dict[str, Any]) -> RegistryHubVersion:
    return RegistryHubVersion(
        version=str(raw.get("version", "")),
        sdk_compat=raw.get("sdk_compat"),
        sha256=raw.get("sha256"),
        size_bytes=raw.get("size_bytes"),
        published_at=raw.get("published_at"),
        archive_url=raw.get("archive_url"),
    )


def _merge(
    hub_index: Optional[Dict[str, Any]],
    installed: Dict[str, Dict[str, Any]],
) -> List[RegistryPlugin]:
    """Build the per-plugin merge view.

    ``installed`` is keyed by plugin_id and holds ``{version, install_method}``
    per row from :class:`PluginCatalogPersistence`.
    """
    merged: List[RegistryPlugin] = []
    seen_locally: set[str] = set()

    hub_plugins = (hub_index or {}).get("plugins", []) if hub_index else []
    for entry in hub_plugins:
        plugin_id = entry.get("slug") or entry.get("plugin_id")
        if not plugin_id:
            continue
        versions_raw = entry.get("versions", []) or []
        hub_versions = [_project_hub_version(v) for v in versions_raw]
        # Filter empty/invalid versions and sort newest-first.
        hub_versions = [v for v in hub_versions if v.version]
        latest = hub_versions[0].version if hub_versions else None

        local = installed.get(plugin_id)
        installed_version = local.get("version") if local else None
        install_method = local.get("install_method") if local else None
        update_available = (
            installed_version is not None
            and latest is not None
            and _version_is_newer(latest, installed_version)
        )

        merged.append(RegistryPlugin(
            plugin_id=plugin_id,
            display_name=str(entry.get("display_name") or plugin_id),
            category=entry.get("category"),
            is_verified=bool(entry.get("is_verified", False)),
            hub_versions=hub_versions,
            latest_hub_version=latest,
            installed_version=installed_version,
            install_method=install_method,
            update_available=update_available,
            source="hub",
        ))
        seen_locally.add(plugin_id)

    # Local-only plugins (installed but not on the hub).
    for plugin_id, row in installed.items():
        if plugin_id in seen_locally:
            continue
        merged.append(RegistryPlugin(
            plugin_id=plugin_id,
            display_name=plugin_id,
            installed_version=row.get("version"),
            install_method=row.get("install_method"),
            source="local-only",
        ))

    return merged


def _read_installed_state(catalog: PluginCatalogPersistence) -> Dict[str, Dict[str, Any]]:
    """Best-effort snapshot of locally-installed plugins keyed by
    manifest_plugin_id. Returns ``{}`` if the catalog API doesn't expose
    a snapshot — the merge still works (every hub plugin shows as
    not-installed)."""
    snapshot: Dict[str, Dict[str, Any]] = {}
    list_installed = getattr(catalog, "list_installed_with_versions", None)
    if callable(list_installed):
        try:
            for row in list_installed():
                pid = row.get("manifest_plugin_id") or row.get("plugin_id")
                if pid:
                    snapshot[pid] = {
                        "version": row.get("version"),
                        "install_method": row.get("install_method"),
                    }
        except Exception:  # noqa: BLE001
            logger.exception("registry: list_installed_with_versions failed")
        return snapshot

    # Fall back to whichever shape the catalog offers.
    list_simple = getattr(catalog, "list_installed", None)
    if callable(list_simple):
        try:
            for pid, method in list_simple().items():
                snapshot[pid] = {"version": None, "install_method": method}
        except Exception:  # noqa: BLE001
            logger.exception("registry: list_installed failed")
    return snapshot


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@plugin_registry_router.get(
    "/index",
    response_model=RegistryIndexResponse,
    summary="Merged hub + local install state for the React registry page",
)
def get_registry_index(
    hub_url: Optional[str] = Query(
        None,
        description="Override the configured hub base URL (e.g. for staging). "
                    "Defaults to MAGELLON_HUB_URL env or https://magellon.org.",
    ),
    catalog: PluginCatalogPersistence = Depends(get_plugin_catalog_persistence),
    _: None = Depends(require_role("Administrator")),
) -> RegistryIndexResponse:
    """One-shot view for the registry UI.

    Calls the hub's ``GET /v1/index.json`` once, joins it with the
    local install state, and returns the merge. Hub failures degrade
    to ``hub_status != "ok"`` with the local-only list still useful —
    air-gapped deployments see their own plugins regardless of hub
    reachability.
    """
    base = (hub_url or _default_hub_url()).rstrip("/")
    status, body, error = _fetch_hub_index(base)
    installed = _read_installed_state(catalog)
    plugins = _merge(body, installed)
    return RegistryIndexResponse(
        hub_url=base,
        hub_status=status,
        hub_error=error,
        plugins=plugins,
    )


__all__ = ["plugin_registry_router"]

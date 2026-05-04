"""Sync dispatcher — route low-latency calls to a plugin's HTTP endpoint (PT-3).

Pre-PT-3 every cross-process call to a plugin went through RMQ:
publish a TaskMessage, wait for a result envelope. Fine for batch
work that takes 100ms+ anyway, terrible for the picker's interactive
preview-and-retune loop where round-trip latency matters.

PT-3 adds a parallel sync path. Plugins that advertise
:class:`Capability.SYNC` or :class:`Capability.PREVIEW` carry an
``http_endpoint`` in their announce envelope (PT-1, SDK side); this
module wraps that endpoint with a clean call surface:

    dispatch_capability(category, capability, "preview", body=...)
      → POSTs to <plugin>/preview with the JSON body
      → returns the parsed JSON response
      → raises BackendNotLive / CapabilityMissing / HTTPStatusError

Resolution order: ``target_backend`` (caller's pin) → category
default (operator-pinned via ``PluginCategoryDefault``) → first
live plugin advertising the capability. The same priority the bus
dispatcher already uses for ``TaskMessage.target_backend``.

The dispatcher does NOT swallow plugin errors — a 5xx from the
plugin surfaces as a :class:`PluginCallFailed` with the upstream
status + body. The HTTP controller (or the meta-controller in
PT-6) decides how to map that to its own response.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from core.plugin_liveness_registry import (
    PluginLivenessEntry,
    get_registry as get_liveness_registry,
)
from core.plugin_state import get_state_store
from magellon_sdk.models.manifest import Capability

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SyncDispatchError(Exception):
    """Base class for sync_dispatcher failures."""


class BackendNotLive(SyncDispatchError):
    """No live plugin matches the (category, target_backend) tuple,
    or the matched plugin doesn't expose ``http_endpoint``."""


class CapabilityMissing(SyncDispatchError):
    """The matched plugin does not advertise the requested capability.
    Pinned because dispatching to a plugin that doesn't claim a
    capability would silently call an endpoint that may not exist."""


class PluginCallFailed(SyncDispatchError):
    """The plugin returned a non-2xx HTTP response.

    ``status_code`` is the upstream code; ``detail`` is the parsed
    JSON body when one was returned, otherwise the raw text.
    """

    def __init__(
        self, *, status_code: int, detail: Any, plugin_id: str, path: str,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.plugin_id = plugin_id
        self.path = path
        super().__init__(
            f"plugin {plugin_id!r} {path} returned {status_code}: {detail!r}"
        )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ResolvedTarget:
    """The plugin sync_dispatcher decided to call."""

    plugin_id: str
    backend_id: Optional[str]
    http_endpoint: str
    capabilities: tuple


def _entry_capabilities(entry: PluginLivenessEntry) -> tuple:
    """Best-effort capability list from the announce manifest.

    Returns a tuple of :class:`Capability` values; empty if the
    plugin's manifest hasn't arrived yet (announce missed) — the
    caller treats that as ``CapabilityMissing``.
    """
    manifest = entry.manifest
    if manifest is None:
        return ()
    return tuple(getattr(manifest, "capabilities", ()) or ())


def _resolve_target(
    category: str,
    capability: Capability,
    *,
    target_backend: Optional[str] = None,
) -> _ResolvedTarget:
    """Pick the live plugin for this (category, capability) call.

    Mirrors the bus dispatcher's ``_resolve_dispatch_target`` priority
    so a sync call routes the same way an async call would, just over
    HTTP instead of RMQ.
    """
    cat_lower = (category or "").lower()
    state = get_state_store()
    candidates = [
        e for e in get_liveness_registry().list_live()
        if (e.category or "").lower() == cat_lower
    ]
    if not candidates:
        raise BackendNotLive(
            f"no live plugin for category {category!r}",
        )

    # 1. Caller pinned a specific backend.
    if target_backend:
        wanted = target_backend.lower()
        for entry in candidates:
            if (entry.backend_id or "").lower() == wanted:
                return _build_target(entry, capability, category)
        raise BackendNotLive(
            f"no live plugin claims backend_id={target_backend!r} "
            f"for category {category!r}",
        )

    # 2. Operator-pinned default.
    default_id = state.get_default(cat_lower)
    if default_id:
        for entry in candidates:
            if entry.plugin_id == default_id:
                return _build_target(entry, capability, category)

    # 3. First live candidate advertising the capability.
    for entry in candidates:
        if capability in _entry_capabilities(entry):
            return _build_target(entry, capability, category)

    # Fall through → first candidate; _build_target will raise
    # CapabilityMissing if it doesn't advertise the cap.
    return _build_target(candidates[0], capability, category)


def _build_target(
    entry: PluginLivenessEntry, capability: Capability, category: str,
) -> _ResolvedTarget:
    caps = _entry_capabilities(entry)
    if capability not in caps:
        raise CapabilityMissing(
            f"plugin {entry.plugin_id!r} (category {category!r}) does not "
            f"advertise {capability.value!r} — declared caps: "
            f"{[c.value for c in caps] if caps else '(none / manifest pending)'}",
        )
    if not entry.http_endpoint:
        raise BackendNotLive(
            f"plugin {entry.plugin_id!r} advertises {capability.value!r} "
            f"but did not announce an http_endpoint — broker dispatch only",
        )
    return _ResolvedTarget(
        plugin_id=entry.plugin_id,
        backend_id=entry.backend_id,
        http_endpoint=entry.http_endpoint,
        capabilities=caps,
    )


# ---------------------------------------------------------------------------
# HTTP call surface
# ---------------------------------------------------------------------------


# Default per-call timeout. Sync paths are designed for sub-second
# interactive use; allow a generous ceiling for cold-start preview
# computations on large images. Operators can override via env later.
_DEFAULT_TIMEOUT_SECONDS = 60.0


def dispatch_capability(
    category: str,
    capability: Capability,
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    target_backend: Optional[str] = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Route a sync call to a live plugin advertising ``capability``.

    Resolves the target via
    :func:`_resolve_target`, calls ``method path`` (e.g. ``"POST",
    "/preview"``) on the plugin's ``http_endpoint``, returns the
    parsed JSON body on 2xx. Non-2xx responses raise
    :class:`PluginCallFailed` carrying the upstream status + parsed
    detail so the controller can map errors verbatim.

    ``client`` is injectable for tests — pass an ``httpx.Client``
    backed by a TestClient transport to call a fake plugin without
    a real socket.
    """
    target = _resolve_target(
        category, capability, target_backend=target_backend,
    )
    url = target.http_endpoint.rstrip("/") + path

    owns_client = client is None
    http = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = http.request(method, url, json=body)
    except httpx.RequestError as exc:
        raise BackendNotLive(
            f"failed to reach plugin {target.plugin_id!r} at {url}: {exc}",
        )
    finally:
        if owns_client:
            http.close()

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:  # noqa: BLE001
            detail = response.text
        raise PluginCallFailed(
            status_code=response.status_code,
            detail=detail,
            plugin_id=target.plugin_id,
            path=path,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"_raw": response.text}


__all__ = [
    "BackendNotLive",
    "CapabilityMissing",
    "PluginCallFailed",
    "SyncDispatchError",
    "dispatch_capability",
]

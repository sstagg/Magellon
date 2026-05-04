"""Sync dispatcher — route low-latency calls to a plugin's HTTP endpoint.

Pre-PT-3 every cross-process call to a plugin went through RMQ:
publish a TaskMessage, wait for a result envelope. Fine for batch
work that takes 100ms+ anyway, terrible for the picker's interactive
preview-and-retune loop where round-trip latency matters.

This module adds a parallel sync path. Plugins that advertise
:class:`Capability.SYNC` or :class:`Capability.PREVIEW` carry an
``http_endpoint`` in their announce envelope; this module wraps
that endpoint with a clean call surface:

    dispatch_capability(category, capability, "POST", "/preview", body=...)
      → POSTs to <plugin>/preview with the JSON body
      → returns the parsed JSON response
      → raises BackendNotLive / CapabilityMissing / PluginCallFailed

Resolution priority (mirrors the bus dispatcher):

  1. ``target_backend`` (caller's pin)
  2. ``instance_id`` (sticky routing — preview_id → instance_id pin)
  3. operator-pinned category default IF that default advertises the
     capability AND is enabled
  4. first live, enabled candidate advertising the capability

Steps 3 and 4 skip disabled plugins (operator hit /disable). The
old version used to bypass the enabled check on the sync path —
restored here so /dispatch routing matches /plugins/{id}/jobs.

The dispatcher does NOT swallow plugin errors — a 5xx from the
plugin surfaces as :class:`PluginCallFailed` with the upstream
status + body. The HTTP controller decides how to map that.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from cachetools import TTLCache

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
    or the matched plugin doesn't expose ``http_endpoint``, or the
    matched plugin is disabled."""


class CapabilityMissing(SyncDispatchError):
    """The matched plugin does not advertise the requested capability."""


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
# Sticky preview routing — preview_id → instance_id pin (Reviewer A).
#
# PREVIEW state is stored in-process per-plugin replica. With one
# replica everything works; with two, ``POST /preview`` lands on A
# while the retune slider tick lands on B → 404. Pin the
# responding replica's instance_id at preview time and route
# subsequent retune/delete to the same one.
#
# 10-minute TTL mirrors the plugin's own TTLCache so a stale
# mapping disappears at the same time as the plugin's cached
# score maps. Bounded at 1000 entries (each is two ~36-char
# strings — negligible memory).
# ---------------------------------------------------------------------------

_PREVIEW_TTL_SECONDS = 600
_PREVIEW_MAX_ENTRIES = 1000
_preview_routes: TTLCache[str, str] = TTLCache(
    maxsize=_PREVIEW_MAX_ENTRIES, ttl=_PREVIEW_TTL_SECONDS,
)
_preview_routes_lock = threading.Lock()


def remember_preview_route(preview_id: str, instance_id: str) -> None:
    """Record which replica owns a preview's cached state."""
    with _preview_routes_lock:
        _preview_routes[preview_id] = instance_id


def lookup_preview_route(preview_id: str) -> Optional[str]:
    """Return the instance_id that owns this preview, or ``None`` if
    the preview is unknown / TTL-expired."""
    with _preview_routes_lock:
        return _preview_routes.get(preview_id)


def forget_preview_route(preview_id: str) -> None:
    """Drop the mapping. Called on DELETE /preview/{id} so a
    follow-up retune resolves fresh (and 404s cleanly)."""
    with _preview_routes_lock:
        _preview_routes.pop(preview_id, None)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ResolvedTarget:
    """The plugin sync_dispatcher decided to call."""

    plugin_id: str
    instance_id: str
    backend_id: Optional[str]
    http_endpoint: str
    capabilities: tuple


def _entry_capabilities(entry: PluginLivenessEntry) -> tuple:
    """Best-effort capability list from the announce manifest."""
    manifest = entry.manifest
    if manifest is None:
        return ()
    return tuple(getattr(manifest, "capabilities", ()) or ())


def _is_enabled(entry: PluginLivenessEntry) -> bool:
    """Reviewer B: skip operator-disabled plugins on the sync path.

    The bus dispatcher's ``_resolve_dispatch_target`` raises 409 for
    disabled plugins; the sync path used to silently route to them.
    Match the bus behaviour — disabled plugins are invisible to the
    resolver. State store keys on the bare plugin_id.
    """
    return get_state_store().is_enabled(entry.plugin_id)


def _resolve_target(
    category: str,
    capability: Capability,
    *,
    target_backend: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> _ResolvedTarget:
    """Pick the live plugin for this (category, capability) call.

    See module docstring for priority. ``instance_id`` is the new
    sticky-routing seam — when set, only the matching replica is
    considered (used by the retune/delete preview flow).
    """
    cat_lower = (category or "").lower()
    candidates = [
        e for e in get_liveness_registry().list_live()
        if (e.category or "").lower() == cat_lower
    ]
    if not candidates:
        raise BackendNotLive(
            f"no live plugin for category {category!r}",
        )

    # 1. Sticky preview pin — must hit the same replica that owns
    # the cached state. No fallback: routing to a different replica
    # would 404 in the plugin (preview_id doesn't exist there).
    if instance_id:
        for entry in candidates:
            if entry.instance_id == instance_id:
                return _build_target(entry, capability, category)
        raise BackendNotLive(
            f"replica {instance_id!r} for category {category!r} is no longer "
            f"live — its cached preview state is gone (TTL or restart)",
        )

    # 2. Caller pinned a specific backend.
    if target_backend:
        wanted = target_backend.lower()
        for entry in candidates:
            if (entry.backend_id or "").lower() != wanted:
                continue
            if not _is_enabled(entry):
                raise BackendNotLive(
                    f"backend {target_backend!r} for category {category!r} "
                    f"is disabled (operator paused dispatch)",
                )
            return _build_target(entry, capability, category)
        raise BackendNotLive(
            f"no live plugin claims backend_id={target_backend!r} "
            f"for category {category!r}",
        )

    # 3. Operator-pinned default — but only if it ALSO advertises the
    # requested capability AND is enabled. Reviewer C: pre-fix this
    # was a hard return that fell into _build_target, raising
    # CapabilityMissing on a default-with-SYNC-but-not-PREVIEW (or
    # disabled default), preventing fall-through to step 4. The whole
    # point of the backend axis is that a category can have one
    # backend serving SYNC and a different one serving PREVIEW.
    state = get_state_store()
    default_id = state.get_default(cat_lower)
    if default_id:
        for entry in candidates:
            if entry.plugin_id != default_id:
                continue
            if (
                capability in _entry_capabilities(entry)
                and _is_enabled(entry)
                and entry.http_endpoint
            ):
                return _build_target(entry, capability, category)
            # Default lacks the capability / is disabled / has no
            # http_endpoint — fall through to step 4 instead of
            # raising.
            break

    # 4. First live, enabled candidate advertising the capability.
    # Preserve specific error semantics by tracking why we rejected
    # each candidate: the test suite (and operators reading 503
    # bodies) want "no http_endpoint" to differ from "no plugin
    # advertises the capability."
    capability_match: Optional[PluginLivenessEntry] = None
    capability_match_disabled = False
    for entry in candidates:
        if capability not in _entry_capabilities(entry):
            continue
        if not _is_enabled(entry):
            capability_match_disabled = True
            continue
        capability_match = entry
        break

    if capability_match is not None:
        # _build_target raises BackendNotLive if http_endpoint is
        # missing — the right error class for this case.
        return _build_target(capability_match, capability, category)

    if capability_match_disabled:
        raise BackendNotLive(
            f"every plugin in category {category!r} advertising "
            f"{capability.value!r} is disabled (operator paused dispatch)",
        )
    raise CapabilityMissing(
        f"no live plugin in category {category!r} advertises "
        f"{capability.value!r}",
    )


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
        instance_id=entry.instance_id,
        backend_id=entry.backend_id,
        http_endpoint=entry.http_endpoint,
        capabilities=caps,
    )


# ---------------------------------------------------------------------------
# HTTP call surface — pooled client (Reviewer D)
# ---------------------------------------------------------------------------

# Default per-call timeout. Sync paths are designed for sub-second
# interactive use; allow a generous ceiling for cold-start preview
# computations. Per-call overrides in dispatch_capability(timeout_seconds=).
_DEFAULT_TIMEOUT_SECONDS = 60.0

# Reviewer D: a fresh httpx.Client per dispatch_capability call did
# a TCP handshake every time, killing retune's sub-100ms target. Use
# one process-wide pooled client; per-call timeout passes through to
# request(). max_keepalive_connections=20 covers a few concurrent
# sliders + a batch loop without hoarding sockets.
_POOL_LIMITS = httpx.Limits(
    max_connections=50, max_keepalive_connections=20, keepalive_expiry=30.0,
)
_pooled_client: Optional[httpx.Client] = None
_pooled_client_lock = threading.Lock()


def _get_pooled_client() -> httpx.Client:
    global _pooled_client
    if _pooled_client is None:
        with _pooled_client_lock:
            if _pooled_client is None:
                _pooled_client = httpx.Client(limits=_POOL_LIMITS)
    return _pooled_client


def reset_pooled_client() -> None:
    """Test helper — closes the cached client so the next call
    rebuilds it. Production code never calls this."""
    global _pooled_client
    with _pooled_client_lock:
        if _pooled_client is not None:
            _pooled_client.close()
            _pooled_client = None


def dispatch_capability(
    category: str,
    capability: Capability,
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    target_backend: Optional[str] = None,
    instance_id: Optional[str] = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Route a sync call to a live plugin advertising ``capability``.

    Resolves the target via :func:`_resolve_target`, calls
    ``method path`` (e.g. ``"POST", "/preview"``) on the plugin's
    ``http_endpoint``, returns the parsed JSON body on 2xx. Non-2xx
    responses raise :class:`PluginCallFailed` carrying the upstream
    status + parsed detail.

    ``instance_id`` pins resolution to a specific replica (sticky
    preview routing). ``client`` is injectable for tests; production
    uses the module-level pooled client.
    """
    target = _resolve_target(
        category, capability,
        target_backend=target_backend, instance_id=instance_id,
    )
    url = target.http_endpoint.rstrip("/") + path

    http = client or _get_pooled_client()
    try:
        response = http.request(method, url, json=body, timeout=timeout_seconds)
    except httpx.RequestError as exc:
        raise BackendNotLive(
            f"failed to reach plugin {target.plugin_id!r} at {url}: {exc}",
        )

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
    parsed: Dict[str, Any]
    if not response.content:
        parsed = {}
    else:
        try:
            parsed = response.json()
        except ValueError:
            parsed = {"_raw": response.text}

    # Sticky preview routing: stash the originating replica's
    # instance_id under the response's preview_id, so retune /
    # delete pin to the same replica. Only the PREVIEW capability's
    # /preview endpoint emits a preview_id; other paths skip this.
    preview_id = parsed.get("preview_id") if isinstance(parsed, dict) else None
    if (
        capability is Capability.PREVIEW
        and method.upper() == "POST"
        and path.endswith("/preview")
        and isinstance(preview_id, str)
    ):
        remember_preview_route(preview_id, target.instance_id)

    return parsed


__all__ = [
    "BackendNotLive",
    "CapabilityMissing",
    "PluginCallFailed",
    "SyncDispatchError",
    "dispatch_capability",
    "forget_preview_route",
    "lookup_preview_route",
    "remember_preview_route",
    "reset_pooled_client",
]

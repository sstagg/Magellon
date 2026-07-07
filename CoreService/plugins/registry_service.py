"""Registry lookups + capability-snapshot assembly for the plugins API.

Everything here reads the liveness registry / operator state store /
DB catalog and resolves plugin identifiers to entries, categories, and
schemas. No routes — the controller modules stay thin on top of this.
"""
from __future__ import annotations

import uuid
from datetime import datetime as _datetime, timezone as _timezone
from typing import Any, Dict, Optional

# Sentinel for max() over heartbeat datetimes; lets entries without a
# heartbeat sort below entries with one without raising on None compares.
_MIN_DT = _datetime.min.replace(tzinfo=_timezone.utc)

from fastapi import HTTPException

from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.plugin_state import get_state_store
from magellon_sdk import __version__ as sdk_version
from magellon_sdk.categories.contract import CATEGORIES, CategoryContract
from magellon_sdk.models import IsolationLevel, Transport

from plugins.schemas import (
    _BackendSummary,
    _CapabilitiesResponse,
    _CategoryCapabilities,
)


def build_capabilities_response() -> _CapabilitiesResponse:
    """Single-shot snapshot for the dispatcher and the UI.

    For each known :class:`CategoryContract` we list every live backend
    (deduplicated by ``(category, backend_id)``, replicas counted),
    annotate the operator-pinned default, and embed the category's
    canonical input/output JSON Schemas. Reads from the same liveness
    registry + state store the dispatcher consults — no separate
    cache, no risk of drift.
    """
    state = get_state_store()

    # Group live entries by (category, backend_id). Replicas (same
    # plugin_id with different instance_ids) collapse into one summary
    # row with ``live_replicas`` counted.
    by_category_backend: Dict[str, Dict[str, list]] = {}
    for entry in get_liveness_registry().list_live():
        cat_key = (entry.category or "").lower()
        backend_key = (entry.backend_id or entry.plugin_id or "").lower() or "unknown"
        by_category_backend.setdefault(cat_key, {}).setdefault(backend_key, []).append(entry)

    response_categories: list[_CategoryCapabilities] = []
    for code, contract in sorted(CATEGORIES.items(), key=lambda kv: kv[0]):
        cat_key = contract.category.name.lower()
        default_backend = state.get_default(cat_key)
        backends = []
        for backend_key, entries in sorted(by_category_backend.get(cat_key, {}).items()):
            # Pick a representative entry for manifest fields. All
            # replicas of one backend share manifest/version, so any is
            # equivalent; we take the most recent heartbeat for stability.
            rep = max(
                entries,
                key=lambda e: e.last_heartbeat or _MIN_DT,
            )
            manifest = rep.manifest
            info = manifest.info if manifest is not None else None
            short_id = rep.plugin_id
            composed_id = (
                short_id if "/" in short_id else f"{cat_key}/{short_id}"
            )
            is_default = state.get_default(cat_key) == short_id
            backends.append(_BackendSummary(
                backend_id=backend_key,
                plugin_id=composed_id,
                name=short_id,
                version=(info.version if info else rep.plugin_version) or "?",
                schema_version=(info.schema_version if info else "1") or "1",
                description=(info.description if info else "") or "",
                developer=(info.developer if info else "") or "",
                capabilities=list(manifest.capabilities) if manifest else [],
                isolation=manifest.isolation if manifest else IsolationLevel.CONTAINER,
                default_transport=(
                    manifest.default_transport if manifest else Transport.RMQ
                ),
                live_replicas=len(entries),
                enabled=state.is_enabled(short_id),
                is_default_for_category=is_default,
                task_queue=rep.task_queue,
            ))


        # X.9: deterministic ordering — default backend first, then
        # alphabetical by backend_id. UIs can render straight from this
        # without re-sorting, and golden / contract tests get a stable
        # response shape across runs.
        backends.sort(key=lambda b: (
            0 if b.is_default_for_category else 1,
            b.backend_id,
        ))

        # Best-effort JSON Schema for the category I/O. Some
        # CategoryContract.input_model classes may not emit clean
        # JSON Schema (exotic types); failing here would break the
        # whole endpoint, so swallow.
        try:
            input_schema = (
                contract.input_model.model_json_schema() if contract.input_model else None
            )
        except Exception:  # noqa: BLE001
            input_schema = None
        try:
            output_schema = (
                contract.output_model.model_json_schema() if contract.output_model else None
            )
        except Exception:  # noqa: BLE001
            output_schema = None

        response_categories.append(_CategoryCapabilities(
            code=code,
            name=contract.category.name,
            description=contract.category.description,
            default_backend=default_backend,
            backends=backends,
            input_schema=input_schema,
            output_schema=output_schema,
            subject_kind=contract.subject_kind,
            produces_subject_kind=contract.produces_subject_kind,
            input_subjects=dict(contract.input_subjects),
            output_subjects=dict(contract.output_subjects),
            # Gradio-style examples — surfaced for the React test panel
            # so operators can pre-fill the form in one click. Empty
            # list when the contract hasn't authored any yet.
            examples=[
                {"name": ex.name, "description": ex.description, "values": ex.values}
                for ex in contract.examples
            ],
        ))

    return _CapabilitiesResponse(
        sdk_version=sdk_version,
        categories=response_categories,
    )


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _strip_category_prefix(plugin_id: str) -> str:
    """Accept both ``plugin_id`` and ``<category>/<plugin_id>`` forms.

    The discovery list uses the composed form for UI uniqueness; the
    liveness registry + state store key on the bare plugin_id.
    """
    return plugin_id.split("/", 1)[1] if "/" in plugin_id else plugin_id


def _live_entry(plugin_id: str):
    """Find the liveness entry for a plugin or 404. Replaces the
    pre-PI-6 ``_require_plugin`` which read from the in-process
    registry — now everything is a broker plugin."""
    short = _strip_category_prefix(plugin_id)
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id in (short, plugin_id):
            return entry
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


def _category_for_plugin(short_id: str) -> Optional[str]:
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id:
            return entry.category
    return None


def _category_contract_for_plugin(
    plugin_id: str, registry=None,
) -> Optional[CategoryContract]:
    """Resolve ``plugin_id`` → :class:`CategoryContract` tolerantly.

    Schema is a property of the **category**, not the running instance,
    so we should be able to answer ``GET /plugins/{id}/schema/input``
    on a stopped or never-started plugin too. Resolution order:

      1. Live registry — bare or composed runtime form
         ("template-picker" or "particle_picking/template-picker").
         Covers running plugins; fastest path.
      2. DB catalog — match against ``manifest_plugin_id`` (the slug
         the operator typed when installing) or ``oid`` (the stable
         UUID). Covers installed-but-stopped plugins, and accepts
         the oid form as a stable alternative for free.

    Returns ``None`` only when no resolver matched — the endpoint then
    400s/404s as appropriate. Production rollouts should never see
    None for a plugin that's actually installed.

    Distinct from :func:`_category_for_plugin` (further up) which
    returns just the category-name string for the live registry only.
    Different concerns, different return shapes — keep them separate.

    ``registry`` lets the back-compat shim in ``plugins.controller``
    thread through a patched liveness registry (tests patch
    ``plugins.controller.get_liveness_registry``); ``None`` reads the
    process-wide singleton.
    """
    reg = registry if registry is not None else get_liveness_registry()
    short = _strip_category_prefix(plugin_id)
    # 1. Live registry
    for entry in reg.list_live():
        if entry.plugin_id in (short, plugin_id):
            return _category_contract_by_name(entry.category)
    # 2. DB catalog — covers installed-but-stopped + oid form
    category = _category_for_plugin_from_db(plugin_id, short)
    if category:
        return _category_contract_by_name(category)
    return None


# Back-compat alias — the pre-2026-05 helper was named ``_category_for_live_plugin``
# (live-registry only). The new resolver is strictly a superset: it
# covers the same live path plus a DB fallback. Aliasing keeps any
# callers that imported the old name working without churn.
_category_for_live_plugin = _category_contract_for_plugin


def _category_for_plugin_from_db(plugin_id: str, short: str) -> Optional[str]:
    """DB-backed identifier → category name resolver.

    Tries (in order): ``manifest_plugin_id == short``,
    ``manifest_plugin_id == plugin_id``, ``oid == plugin_id`` (parsed
    as UUID), ``name == short``. Returns ``None`` when none match.
    Reads on a short-lived session so this stays cheap to call from
    request handlers.
    """
    from sqlalchemy.orm import Session as _Session
    from database import session_local
    from models.sqlalchemy_models import Plugin

    db: _Session = session_local()
    try:
        for candidate in (short, plugin_id):
            row = (
                db.query(Plugin)
                .filter(Plugin.manifest_plugin_id == candidate)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        # oid path — only attempt if the input parses as UUID; cheap
        # to skip otherwise so we don't try a UUID query for every
        # slug request.
        try:
            oid = uuid.UUID(plugin_id)
        except (ValueError, AttributeError):
            oid = None
        if oid is not None:
            row = (
                db.query(Plugin)
                .filter(Plugin.oid == oid)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        # Last-ditch fallback: match by display ``name`` (the announce
        # form before P5 used the human name). Bounded scan; tens of
        # rows in production. Skip if short is empty.
        if short:
            row = (
                db.query(Plugin)
                .filter(Plugin.name == short)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        return None
    finally:
        db.close()


def _live_schema_for_plugin(plugin_id: str, *, kind: str) -> Optional[Dict[str, Any]]:
    """Pull the plugin's announced JSON schema from the live registry,
    falling back to the persisted catalog row when the live entry is
    cold.

    PE2-UI (2026-05-12). When a plugin announces with
    :attr:`Announce.input_schema` / ``output_schema`` set, the
    registry caches the dict and we hand it back here so the runner
    page renders the plugin's own rich form. ``kind`` is "input" or
    "output".

    Tiered resolution (2026-05-13):
      1. Live registry — populated by the announce listener; cleared
         on CoreService restart.
      2. Persisted ``Plugin.manifest_json`` — written by
         ``record_announce`` so the schema survives a CoreService
         restart and the gap before the next announce.
      3. Returns ``None`` so the caller falls back to the category
         contract's input model.
    """
    short = _strip_category_prefix(plugin_id)
    attr = "input_schema" if kind == "input" else "output_schema"
    # Tier 1: live registry.
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id in (short, plugin_id):
            value = getattr(entry, attr, None)
            if value is not None:
                return value
    # Tier 2: DB row from a prior announce. Match by manifest_plugin_id
    # (install slug) or the announce-derived name. Best-effort — a DB
    # hiccup here returns None and the caller falls back to the
    # category contract.
    try:
        from database import session_local
        from models.sqlalchemy_models import Plugin
        with session_local() as db:
            row = (
                db.query(Plugin)
                .filter(
                    (Plugin.manifest_plugin_id == short)
                    | (Plugin.manifest_plugin_id == plugin_id)
                    | (Plugin.name == short)
                    | (Plugin.name == plugin_id)
                )
                .first()
            )
            if row and row.manifest_json:
                value = row.manifest_json.get(attr)
                if value is not None:
                    return value
    except Exception:  # noqa: BLE001 — never fail the endpoint on DB hiccups
        pass
    return None


def _find_broker_plugin(plugin_id: str, registry=None) -> Optional[CategoryContract]:
    """Look up a broker plugin by plugin_id, resolve its category contract.

    Plugins in the liveness registry use whatever ``plugin_id`` they
    announced (typically ``info.name``, e.g. ``"FFT — magnitude spectrum"``);
    the ``/plugins/`` list prepends the category (e.g.
    ``"fft/FFT — magnitude spectrum"``); the manifest's bare slug
    (e.g. ``"fft"``) is a third valid form an operator might type.
    Accept all three; returns the :class:`CategoryContract` — that's
    what we need for dispatch (category-scoped TaskRoute + input_model
    for validation).

    Match order:
      1. ``entry.plugin_id == plugin_id`` (composed or runtime form match)
      2. ``entry.plugin_id == short_id`` (composed form stripped to runtime)
      3. ``entry.backend_id == short_id`` (manifest slug match — covers
         e.g. ``/plugins/fft/jobs`` where the runtime form differs)

    ``registry`` lets the back-compat shim in ``plugins.controller``
    thread through a patched liveness registry (tests patch
    ``plugins.controller.get_liveness_registry``); ``None`` reads the
    process-wide singleton.
    """
    reg = registry if registry is not None else get_liveness_registry()
    short_id = _strip_category_prefix(plugin_id)
    for entry in reg.list_live():
        if entry.plugin_id == short_id or entry.plugin_id == plugin_id:
            return _category_contract_by_name(entry.category)
    # Slug fallback — matches the install-time backend_id rather than
    # the announce-time plugin_id. Covers the common case where the
    # plugin announces under its display name but the URL/UI refers
    # to it by its manifest slug.
    for entry in reg.list_live():
        if entry.backend_id and entry.backend_id == short_id:
            return _category_contract_by_name(entry.category)
    return None


def _normalize_category_key(s: str) -> str:
    """Collapse spaces / underscores / case so display-form names
    (``"Particle Picking"``) and slug-form names (``"particle_picking"``)
    compare equal. Plugin manifests use the slug form; ``CategoryContract``
    declares the display form. Without this, the DB-fallback resolver
    can't bridge the two."""
    return "".join(s.lower().split()).replace("_", "").replace("-", "")


def _category_contract_by_name(category_name: str) -> Optional[CategoryContract]:
    """Find a :class:`CategoryContract` by its category name.

    :data:`CATEGORIES` is keyed by code; brokers announce by name. Scan
    once — there are only a handful of categories in practice. The
    matcher is space/underscore/case insensitive so plugin manifests
    can use the slug form (``"particle_picking"``) and the contract
    side can use the display form (``"Particle Picking"``) without
    coordination.
    """
    target = _normalize_category_key(category_name)
    for contract in CATEGORIES.values():
        if _normalize_category_key(contract.category.name) == target:
            return contract
    return None

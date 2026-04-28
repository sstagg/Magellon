"""Generic plugin HTTP router — discovery + batch submission for any plugin.

Endpoints:
    GET  /plugins/                              — list registered plugins
    GET  /plugins/{plugin_id}/info              — plugin metadata
    GET  /plugins/{plugin_id}/health            — liveness probe
    GET  /plugins/{plugin_id}/requirements      — dependency check
    GET  /plugins/{plugin_id}/schema/input      — input JSON schema
    GET  /plugins/{plugin_id}/schema/output     — output JSON schema
    POST /plugins/{plugin_id}/jobs              — submit one job
    POST /plugins/{plugin_id}/jobs/batch        — fan out over N images
    GET  /plugins/jobs                          — list jobs (optional plugin filter)
    GET  /plugins/jobs/{job_id}                 — job detail

Plugin-specific routes (preview/retune for template-picker, etc.) remain on
the plugin's own router. This controller covers everything that's uniform
across plugins.
"""
from __future__ import annotations

import asyncio
import io
import logging
import uuid
import zipfile
from datetime import datetime as _datetime, timezone as _timezone
from typing import Any, Dict, List, Literal, Optional

# Sentinel for max() over heartbeat datetimes; lets entries without a
# heartbeat sort below entries with one without raising on None compares.
_MIN_DT = _datetime.min.replace(tzinfo=_timezone.utc)

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from core.installed_plugins import get_installed_registry
from core.plugin_catalog import get_catalog
from core.plugin_docker_runner import (
    DockerNotAvailable,
    VolumeMount,
    get_runner as get_docker_runner,
)
from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.plugin_state import get_state_store
from magellon_sdk import __version__ as sdk_version
from magellon_sdk.archive import (
    PluginArchiveManifest,
    SchemaVersionError,
    SdkCompatError,
    check_sdk_compat,
    load_manifest_bytes,
)
from magellon_sdk.bus import get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CATEGORIES, CategoryContract
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginManifest,
    TaskMessage,
    TaskStatus,
    Transport,
)
from plugins.registry import registry
from services.job_manager import job_manager

logger = logging.getLogger(__name__)

plugins_router = APIRouter()


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class PluginSummary(BaseModel):
    """Discovery payload — identity + the capability fields a UI / manager
    needs to decide *whether* and *how* to call this plugin.

    The full manifest is also fetchable at /plugins/{id}/manifest, but
    embedding the small high-signal subset here means the discovery
    endpoint is enough to render a plugin picker / health dashboard
    without N round-trips."""
    plugin_id: str
    category: str
    name: str
    version: str
    schema_version: str
    description: str
    developer: str
    # Capability subset surfaced into discovery — full manifest at /manifest
    capabilities: list[Capability] = []
    supported_transports: list[Transport] = []
    default_transport: Transport = Transport.IN_PROCESS
    isolation: IsolationLevel = IsolationLevel.IN_PROCESS
    # How the UI should treat this entry:
    # - ``in-process``: PluginBase subclass living in this CoreService
    #   process; reachable via POST /plugins/{plugin_id}/jobs.
    # - ``broker``: external plugin (Docker container or separate
    #   process) that announced itself on ``magellon.plugins.liveness``;
    #   dispatch flows through the bus, not through this controller's
    #   /jobs endpoint.
    kind: Literal["in-process", "broker"] = "in-process"
    # Operator state (H1). ``enabled`` defaults True until an operator
    # toggles it. ``is_default_for_category`` is derived from the
    # per-category default-impl selection — the UI uses it to render
    # a "Default" badge and to decide which impl a category-scoped
    # dispatch would pick today.
    enabled: bool = True
    is_default_for_category: bool = False
    # Plugin-declared task queue (SDK 1.1+ Announce.task_queue). ``None``
    # for pre-1.1 plugins; the dispatcher falls back to the legacy
    # category-scoped route in that case.
    task_queue: Optional[str] = None


class JobSubmitRequest(BaseModel):
    """Submit one job for a plugin. ``input`` shape is validated by the plugin."""
    input: Dict[str, Any]
    name: Optional[str] = None
    image_id: Optional[str] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None
    """Pin the dispatch to a specific backend within the plugin's
    category (X.1). Only meaningful for broker-dispatched plugins;
    ignored by the in-process path. When set and no live backend
    matches, the controller returns 503 instead of round-robining."""


class BatchSubmitRequest(BaseModel):
    """Fan out the same plugin over many inputs (one job per input)."""
    inputs: List[Dict[str, Any]] = Field(..., min_length=1)
    name: Optional[str] = None
    image_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None


# ---------------------------------------------------------------------------
# Capabilities — one consolidated catalog (X.1)
# ---------------------------------------------------------------------------
#
# UI and dispatcher both need the same picture: which categories exist,
# which backends serve each, which is default. Today this is split across
# GET /plugins/, GET /plugins/categories/defaults, and GET
# /plugins/{id}/manifest — three reads + a join in JS. /capabilities
# returns one snapshot.

class _BackendSummary(BaseModel):
    """One backend serving a category. Folds plugin + manifest + state."""

    backend_id: str
    plugin_id: str
    """``<category>/<short>`` form to match the rest of the discovery API."""
    name: str
    version: str
    schema_version: str
    description: str = ""
    developer: str = ""
    capabilities: list[Capability] = []
    isolation: IsolationLevel = IsolationLevel.IN_PROCESS
    default_transport: Transport = Transport.IN_PROCESS
    live_replicas: int
    enabled: bool
    is_default_for_category: bool
    task_queue: Optional[str] = None


class _CategoryCapabilities(BaseModel):
    code: int
    name: str
    description: str
    default_backend: Optional[str] = None
    backends: list[_BackendSummary] = []
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class _CapabilitiesResponse(BaseModel):
    sdk_version: str
    categories: list[_CategoryCapabilities] = []


@plugins_router.get(
    "/capabilities",
    summary="Consolidated catalog: categories × backends + defaults",
    response_model=_CapabilitiesResponse,
)
async def list_capabilities() -> _CapabilitiesResponse:
    """Single-shot snapshot for the dispatcher and the UI.

    For each known :class:`CategoryContract` we list every live backend
    (deduplicated by ``(category, backend_id)``, replicas counted),
    annotate the operator-pinned default, and embed the category's
    canonical input/output JSON Schemas. Reads from the same liveness
    registry + state store the dispatcher consults — no separate
    cache, no risk of drift.
    """
    state = get_state_store()
    in_process_ids = {entry.plugin_id for entry in registry.list()}

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

        # In-process plugins for this category that haven't shown up in
        # the liveness registry (e.g. before announce wiring lands or
        # in tests). They still serve the category, so list them.
        for in_proc_id in in_process_ids:
            short = in_proc_id.split("/", 1)[1] if "/" in in_proc_id else in_proc_id
            already_listed = any(b.name == short for b in backends)
            entry = registry.get(in_proc_id)
            if entry is None or already_listed:
                continue
            try:
                entry_category = entry.instance.task_category.name.lower()
            except Exception:  # noqa: BLE001
                entry_category = ""
            if entry_category != cat_key:
                continue
            manifest = entry.manifest
            info = manifest.info
            backend_key = (manifest.backend_id or short).lower() or "unknown"
            is_default = state.get_default(cat_key) == short
            backends.append(_BackendSummary(
                backend_id=backend_key,
                plugin_id=in_proc_id if "/" in in_proc_id else f"{cat_key}/{short}",
                name=short,
                version=info.version or "?",
                schema_version=info.schema_version or "1",
                description=info.description or "",
                developer=info.developer or "",
                capabilities=list(manifest.capabilities),
                isolation=manifest.isolation,
                default_transport=manifest.default_transport,
                live_replicas=1,
                enabled=state.is_enabled(short),
                is_default_for_category=is_default,
                task_queue=None,
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
        ))

    return _CapabilitiesResponse(
        sdk_version=sdk_version,
        categories=response_categories,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@plugins_router.get("/", summary="List all registered plugins")
async def list_plugins() -> List[PluginSummary]:
    """List every plugin the liveness registry has seen.

    Post-U1.1, in-process plugins announce themselves at CoreService
    startup (see ``plugins.in_process_announce``), so the liveness
    registry is the single source of truth — no more separate static
    walk. The ``kind`` field is derived by cross-referencing with the
    in-process registry: plugins that also appear there ran inside
    this Python process; the rest are broker plugins (Docker containers
    or separate processes).

    Plugins that announced with ``plugin_id = "CTF Plugin"`` (no
    category prefix) get a composed id ``"{category}/{plugin_id}"`` so
    the UI's plugin-id scheme is uniform. Plugins that already use the
    composed form (the in-process ones) pass through unchanged.
    """
    # Set of plugin_ids known to run in-process — used to label the
    # summary's ``kind`` field. Populated once per request.
    in_process_ids = {entry.plugin_id for entry in registry.list()}

    state = get_state_store()
    summaries: List[PluginSummary] = []
    seen_ids: set[str] = set()

    live_entries = get_liveness_registry().list_live()

    # Auto-seed the per-category default impl: the first live plugin
    # seen for a category becomes its default. Operators can override
    # later via POST /plugins/categories/{category}/default.
    for entry in live_entries:
        if entry.category and state.get_default(entry.category) is None:
            state.set_default(entry.category, entry.plugin_id)

    for entry in live_entries:
        plugin_id = entry.plugin_id
        if "/" not in plugin_id and entry.category:
            plugin_id = f"{entry.category}/{plugin_id}"
        if plugin_id in seen_ids:
            continue
        kind = "in-process" if plugin_id in in_process_ids else "broker"
        enabled = state.is_enabled(entry.plugin_id)
        is_default = state.get_default(entry.category) == entry.plugin_id

        manifest = entry.manifest
        if manifest is not None:
            info = manifest.info
            summaries.append(PluginSummary(
                plugin_id=plugin_id,
                category=entry.category,
                name=entry.plugin_id,
                version=info.version,
                schema_version=info.schema_version or "1",
                description=info.description,
                developer=info.developer,
                capabilities=list(manifest.capabilities),
                supported_transports=list(manifest.supported_transports),
                default_transport=manifest.default_transport,
                isolation=manifest.isolation,
                kind=kind,
                enabled=enabled,
                is_default_for_category=is_default,
                task_queue=entry.task_queue,
            ))
        else:
            # Heartbeat arrived but we missed the Announce (CoreService
            # started after the plugin). Synthesise placeholder metadata
            # — the plugin still shows up, with a hint to re-announce.
            summaries.append(PluginSummary(
                plugin_id=plugin_id,
                category=entry.category,
                name=entry.plugin_id,
                version=entry.plugin_version or "?",
                schema_version="1",
                description="(manifest pending — restart the plugin "
                            "or wait for the next announce)",
                developer="",
                capabilities=[],
                supported_transports=[Transport.RMQ],
                default_transport=Transport.RMQ,
                isolation=IsolationLevel.CONTAINER,
                kind=kind,
                enabled=enabled,
                is_default_for_category=is_default,
                task_queue=entry.task_queue,
            ))
        seen_ids.add(plugin_id)

    return summaries


@plugins_router.get("/{plugin_id:path}/manifest", summary="Plugin capability manifest")
async def plugin_manifest(plugin_id: str) -> PluginManifest:
    """Full capability description — what the plugin needs (resources,
    isolation) and how it can be reached (transports). Remote plugins
    will eventually serve this same shape from their own /manifest, so
    a future PluginManager can consume in-house and remote plugins
    through one model."""
    return _require_plugin(plugin_id).manifest


def _require_plugin(plugin_id: str):
    entry = registry.get(plugin_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")
    return entry


@plugins_router.get("/{plugin_id:path}/info", summary="Plugin metadata")
async def plugin_info(plugin_id: str):
    return _require_plugin(plugin_id).instance.get_info()


@plugins_router.get("/{plugin_id:path}/health", summary="Plugin liveness probe")
async def plugin_health(plugin_id: str):
    return _require_plugin(plugin_id).instance.health_check()


@plugins_router.get("/{plugin_id:path}/requirements", summary="Plugin requirement check")
async def plugin_requirements(plugin_id: str):
    return _require_plugin(plugin_id).instance.check_requirements()


@plugins_router.get("/{plugin_id:path}/schema/input", summary="Plugin input JSON schema")
async def plugin_input_schema(plugin_id: str):
    return _require_plugin(plugin_id).instance.input_schema().model_json_schema()


@plugins_router.get("/{plugin_id:path}/schema/output", summary="Plugin output JSON schema")
async def plugin_output_schema(plugin_id: str):
    return _require_plugin(plugin_id).instance.output_schema().model_json_schema()


# ---------------------------------------------------------------------------
# Job submission — single and batch
# ---------------------------------------------------------------------------

@plugins_router.post("/{plugin_id:path}/jobs", summary="Submit one plugin job (async)")
async def submit_job(plugin_id: str, request: JobSubmitRequest, sid: str | None = None):
    """Dispatch one job.

    U1.3: in-process plugins still run via ``plugin.run()`` in an executor
    (existing code path). Broker plugins dispatch via ``bus.tasks.send`` —
    the plugin's runner (Docker container or separate process) consumes
    the task and publishes the result + step events back. ``job_manager``
    row is the same shape either way; callers don't need to care.
    """
    in_process = _find_in_process_plugin(plugin_id)
    if in_process is not None:
        return await _submit_in_process_job(in_process, request, sid)
    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_job(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@plugins_router.post("/{plugin_id:path}/jobs/batch", summary="Submit a batch of plugin jobs (one per input)")
async def submit_batch(plugin_id: str, request: BatchSubmitRequest, sid: str | None = None):
    if request.image_ids is not None and len(request.image_ids) != len(request.inputs):
        raise HTTPException(
            status_code=422,
            detail="image_ids length must match inputs length when provided",
        )

    in_process = _find_in_process_plugin(plugin_id)
    if in_process is not None:
        return await _submit_in_process_batch(in_process, request, sid)
    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_batch(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_in_process_plugin(plugin_id: str):
    """Static registry lookup. Returns the ``PluginEntry`` or ``None``."""
    return registry.get(plugin_id)


def _find_broker_plugin(plugin_id: str) -> Optional[CategoryContract]:
    """Look up a broker plugin by plugin_id, resolve its category contract.

    Plugins in the liveness registry use whatever ``plugin_id`` they
    announced; the ``/plugins/`` list prepends the category (e.g.
    "fft/FFT Plugin"). Accept both forms here. Returns the
    :class:`CategoryContract` — that's what we need for dispatch
    (category-scoped TaskRoute + input_model for validation).
    """
    short_id = _strip_category_prefix(plugin_id)
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id or entry.plugin_id == plugin_id:
            return _category_contract_by_name(entry.category)
    return None


def _resolve_dispatch_target(
    plugin_id: str, contract: CategoryContract,
    *,
    target_backend: Optional[str] = None,
) -> "PluginLivenessEntry":
    """Pick the live plugin instance that should receive this dispatch.

    Three HTTP-layer failures short-circuit here so callers see a real
    error instead of a silently queued task:

    * ``target_backend`` set but no live plugin claims it → 503.
    * No live impl for this category → 503 (H1.c).
    * Named impl is present but disabled → 409.

    The target has to be both ``enabled`` and in the liveness window.
    A disabled default still counts as the default — we don't silently
    fail over to a different impl — so the UI can surface the real
    state to the operator.

    When ``target_backend`` is set, the backend pin wins over the
    operator-pinned default and over the URL-named impl: the caller
    asked for a specific implementation and silently routing to a
    different one would mask their intent.
    """
    from core.plugin_liveness_registry import PluginLivenessEntry  # local: avoid cycle

    state = get_state_store()
    short_id = _strip_category_prefix(plugin_id)

    # Candidates for this category, from the liveness registry.
    live: list[PluginLivenessEntry] = [
        e for e in get_liveness_registry().list_live()
        if e.category.lower() == contract.category.name.lower()
    ]

    # Backend pin wins. We do not consult the URL-named impl or the
    # operator default — the pin is a binding directive.
    if target_backend:
        wanted = target_backend.lower()
        for e in live:
            if (e.backend_id or "").lower() != wanted:
                continue
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Backend {wanted!r} for category "
                        f"{contract.category.name!r} is disabled"
                    ),
                )
            return e
        raise HTTPException(
            status_code=503,
            detail=(
                f"No live plugin claims backend_id={target_backend!r} for "
                f"category {contract.category.name!r}"
            ),
        )

    # Explicit impl? Must match the URL exactly. Disabled → 409.
    for e in live:
        if e.plugin_id == short_id:
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=f"Plugin {short_id} is disabled",
                )
            return e

    # No explicit impl name — caller passed a category-scoped id.
    # Route to the pinned default if it's live and enabled.
    default_id = state.get_default(contract.category.name.lower())
    if default_id:
        for e in live:
            if e.plugin_id == default_id:
                if not state.is_enabled(e.plugin_id):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Default impl {default_id!r} for category "
                            f"{contract.category.name!r} is disabled"
                        ),
                    )
                return e

    # No default and no explicit id — any live enabled candidate will do.
    for e in live:
        if state.is_enabled(e.plugin_id):
            return e

    raise HTTPException(
        status_code=503,
        detail=(
            f"No live enabled plugin for category "
            f"{contract.category.name!r} — cannot dispatch"
        ),
    )


def _category_contract_by_name(category_name: str) -> Optional[CategoryContract]:
    """Find a :class:`CategoryContract` by its category name.

    :data:`CATEGORIES` is keyed by code; brokers announce by name. Scan
    once — there are only a handful of categories in practice.
    """
    for contract in CATEGORIES.values():
        if contract.category.name.lower() == category_name.lower():
            return contract
    return None


# ---------------------------------------------------------------------------
# In-process dispatch — existing path
# ---------------------------------------------------------------------------

async def _submit_in_process_job(entry, request: JobSubmitRequest, sid: str | None):
    try:
        validated = entry.instance.input_schema().model_validate(request.input)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")

    envelope = job_manager.create_job(
        plugin_id=entry.plugin_id,
        name=request.name or f"{entry.name} job",
        settings=validated.model_dump(mode="json"),
        image_ids=[request.image_id] if request.image_id else None,
        user_id=request.user_id,
        msession_id=request.msession_id,
    )
    asyncio.create_task(_run_generic_job(entry, envelope["job_id"], validated, sid))
    return envelope


async def _submit_in_process_batch(entry, request: BatchSubmitRequest, sid: str | None):
    validated_inputs = []
    for idx, raw in enumerate(request.inputs):
        try:
            validated_inputs.append(entry.instance.input_schema().model_validate(raw))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid input at index {idx}: {exc}")

    envelopes: List[Dict[str, Any]] = []
    for idx, validated in enumerate(validated_inputs):
        image_id = request.image_ids[idx] if request.image_ids else None
        envelope = job_manager.create_job(
            plugin_id=entry.plugin_id,
            name=request.name or f"{entry.name} batch [{idx + 1}/{len(validated_inputs)}]",
            settings=validated.model_dump(mode="json"),
            image_ids=[image_id] if image_id else None,
            user_id=request.user_id,
            msession_id=request.msession_id,
        )
        envelopes.append(envelope)
        asyncio.create_task(_run_generic_job(entry, envelope["job_id"], validated, sid))

    return {"jobs": envelopes, "count": len(envelopes)}


# ---------------------------------------------------------------------------
# Broker dispatch — publish to magellon.tasks.<category> via the bus
# ---------------------------------------------------------------------------

_BROKER_ENVELOPE_SOURCE = "magellon/core_service/plugin_controller"


def _validate_broker_input(contract: CategoryContract, raw: Dict[str, Any]):
    """Validate input against the category's Pydantic input model.

    Contracts like ``CTF``/``FFT``/``MOTIONCOR_CATEGORY`` pin
    ``input_model`` (e.g. ``CtfInput``). ``PARTICLE_PICKER`` doesn't
    pin one yet (see contract.py) — fall back to round-tripping the
    raw dict so dispatch still works for those.
    """
    model = contract.input_model
    if model is None:
        return raw
    try:
        return model.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


def _build_task_dto(
    contract: CategoryContract,
    validated_input,
    task_id: uuid.UUID,
    job_id: str,
    user_id: Optional[str],
    target_backend: Optional[str] = None,
) -> TaskMessage:
    """Wrap a validated input in the TaskMessage the bus transports.

    ``task_id`` must match the one registered with ``job_manager.create_job``;
    otherwise the step-event projector can't link events back to the
    job row and the row stays ``queued`` forever.

    ``target_backend`` rides on the DTO so the dispatcher can route to
    a specific backend's queue. The controller path uses the resolved
    ``target.task_queue`` directly (no round-trip through the
    dispatcher), but the field is still set so the consuming plugin
    can confirm it was the intended recipient.
    """
    data = (
        validated_input.model_dump(mode="json")
        if hasattr(validated_input, "model_dump")
        else validated_input
    )
    return TaskMessage(
        id=task_id,
        worker_instance_id=uuid.uuid4(),
        job_id=uuid.UUID(job_id),
        data=data,
        type=contract.category,
        status=TaskStatus(code=0, name="pending", description="Task is pending"),
        target_backend=target_backend,
    )


def _publish_to_bus(
    contract: CategoryContract, task: TaskMessage, target_queue: Optional[str] = None,
) -> bool:
    """Publish to the target impl's queue (SDK 1.1+) or the legacy
    category-scoped route when no impl-specific queue is known.

    The fallback matters for pre-1.1 plugins whose announce doesn't
    carry ``task_queue``; they still consume from the legacy category
    queue and the binder's legacy_queue_map resolves the route.
    """
    if target_queue:
        route = TaskRoute.named(target_queue)
    else:
        route = TaskRoute.for_category(contract)
    envelope = Envelope.wrap(
        source=_BROKER_ENVELOPE_SOURCE,
        type="magellon.task.dispatch",
        subject=route.subject,
        data=task,
    )
    receipt = get_bus().tasks.send(route, envelope)
    if not receipt.ok:
        logger.error(
            "broker dispatch failed on %s: %s", route.subject, receipt.error,
        )
    return receipt.ok


async def _submit_broker_job(
    plugin_id: str,
    contract: CategoryContract,
    request: JobSubmitRequest,
) -> Dict[str, Any]:
    validated = _validate_broker_input(contract, request.input)
    settings = (
        validated.model_dump(mode="json")
        if hasattr(validated, "model_dump") else validated
    )
    # Resolve the target impl BEFORE creating a job row — that way
    # H1.c's 503 ("no live enabled impl") doesn't leave an orphan
    # queued row behind.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    # Generate the task_id up front so the same id registered with the
    # job_manager rides inside the TaskMessage. The step-event projector
    # needs this linkage to flip the job row's status.
    task_id = uuid.uuid4()

    envelope = job_manager.create_job(
        plugin_id=plugin_id,
        name=request.name or f"{plugin_id} job",
        settings=settings,
        task_ids=[task_id],
        image_ids=[request.image_id] if request.image_id else None,
        user_id=request.user_id,
        msession_id=request.msession_id,
    )
    task = _build_task_dto(
        contract, validated, task_id, envelope["job_id"], request.user_id,
        target_backend=request.target_backend,
    )
    if not _publish_to_bus(contract, task, target.task_queue):
        job_manager.fail_job(envelope["job_id"], error="Failed to publish task to bus")
        raise HTTPException(status_code=502, detail="Failed to publish task to bus")
    return envelope


async def _submit_broker_batch(
    plugin_id: str,
    contract: CategoryContract,
    request: BatchSubmitRequest,
) -> Dict[str, Any]:
    # Up-front validation — fail the whole batch cleanly rather than
    # creating half the jobs then failing mid-flight.
    validated_inputs = [
        _validate_broker_input(contract, raw) for raw in request.inputs
    ]

    # Resolve the target impl once for the whole batch. Rolls any 503
    # (no live impl) / 409 (disabled) before a single job row is
    # created, so a batch never half-lands.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    envelopes: List[Dict[str, Any]] = []
    publish_failures: List[str] = []
    for idx, validated in enumerate(validated_inputs):
        image_id = request.image_ids[idx] if request.image_ids else None
        settings = (
            validated.model_dump(mode="json")
            if hasattr(validated, "model_dump") else validated
        )
        task_id = uuid.uuid4()
        env = job_manager.create_job(
            plugin_id=plugin_id,
            name=request.name or f"{plugin_id} batch [{idx + 1}/{len(validated_inputs)}]",
            settings=settings,
            task_ids=[task_id],
            image_ids=[image_id] if image_id else None,
            user_id=request.user_id,
            msession_id=request.msession_id,
        )
        envelopes.append(env)
        task = _build_task_dto(
            contract, validated, task_id, env["job_id"], request.user_id,
            target_backend=request.target_backend,
        )
        if not _publish_to_bus(contract, task, target.task_queue):
            job_manager.fail_job(env["job_id"], error="Failed to publish task to bus")
            publish_failures.append(env["job_id"])

    if publish_failures:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {len(publish_failures)}/{len(envelopes)} tasks to bus",
        )
    return {"jobs": envelopes, "count": len(envelopes)}


# ---------------------------------------------------------------------------
# Operator state: enable/disable, default-impl selector (H1)
# ---------------------------------------------------------------------------

class _SetDefaultRequest(BaseModel):
    plugin_id: str


def _strip_category_prefix(plugin_id: str) -> str:
    """Accept both ``plugin_id`` and ``<category>/<plugin_id>`` forms.

    The discovery list uses the composed form for UI uniqueness; the
    liveness registry + state store key on the bare plugin_id.
    """
    return plugin_id.split("/", 1)[1] if "/" in plugin_id else plugin_id


def _category_for_plugin(short_id: str) -> Optional[str]:
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id:
            return entry.category
    return None


@plugins_router.post("/{plugin_id:path}/enable", summary="Enable dispatch to a plugin")
async def enable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Allow the dispatcher to route tasks to this plugin.

    Does not start the plugin — it's expected to be announcing already.
    No-op if already enabled. Enables are cheap and idempotent so the
    UI can fire blindly on toggle flip.
    """
    short_id = _strip_category_prefix(plugin_id)
    get_state_store().set_enabled(short_id, True)
    return {"plugin_id": short_id, "enabled": True}


@plugins_router.post("/{plugin_id:path}/disable", summary="Disable dispatch to a plugin")
async def disable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Quiesce a plugin without stopping it.

    The plugin keeps announcing + heartbeating; the dispatcher refuses
    new tasks. In-flight tasks are unaffected — this is a pause switch,
    not a kill switch. A disabled default impl still counts as the
    default for its category; a dispatch attempt returns 503 rather
    than silently promoting another impl.
    """
    short_id = _strip_category_prefix(plugin_id)
    get_state_store().set_enabled(short_id, False)
    return {"plugin_id": short_id, "enabled": False}


@plugins_router.get("/categories/defaults", summary="Per-category default impl map")
async def list_category_defaults() -> Dict[str, Any]:
    """Return current per-category default-impl selections.

    UI uses this to render "Default" badges. Key is lowercase category
    name; value is the plugin_id CoreService will route to when the
    dispatch is category-scoped (no explicit plugin_id in the URL).
    """
    snapshot = get_state_store().snapshot()
    return {"defaults": snapshot["default_impl"]}


@plugins_router.post(
    "/categories/{category}/default",
    summary="Pin the default impl for a category",
)
async def set_category_default(category: str, request: _SetDefaultRequest) -> Dict[str, Any]:
    """Choose which impl handles category-scoped dispatches.

    Category-scoped dispatch means "route a CTF task" without naming an
    impl: we publish to the default impl's task queue. A replacement
    impl (second CTF engine, community upload) can be installed and
    announced without taking traffic until the operator flips this.
    """
    short_id = _strip_category_prefix(request.plugin_id)
    # Validate the plugin is actually live + in this category — fail
    # loudly rather than pin a typo as default.
    cat = _category_for_plugin(short_id)
    if cat is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin {short_id} is not in the live registry — can't make it the default.",
        )
    if cat.lower() != category.lower():
        raise HTTPException(
            status_code=422,
            detail=f"Plugin {short_id} is in category {cat!r}, not {category!r}.",
        )
    get_state_store().set_default(category, short_id)
    return {"category": category.lower(), "default_plugin_id": short_id}


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

class _InstallVolume(BaseModel):
    host_path: str
    container_path: str
    read_only: bool = False


class _InstallPluginRequest(BaseModel):
    """Everything docker run needs. Everything config-ish the plugin
    itself reads from its own settings YAML — not our problem here."""
    image_ref: str = Field(..., description="Docker image ref, e.g. ghcr.io/org/plugin:v1")
    env: Dict[str, str] = Field(default_factory=dict)
    volumes: List[_InstallVolume] = Field(default_factory=list)
    network: Optional[str] = Field(
        default=None,
        description="Docker network name. Use the network RMQ is on "
                    "(e.g. 'magellon_default' under docker-compose) so "
                    "the plugin can resolve rabbitmq by hostname.",
    )


def _ensure_docker() -> None:
    """Fail fast with 503 when the docker CLI / daemon is unreachable.

    Called from every /installed endpoint before we touch the runner —
    better to tell the client "Docker unavailable" than surface a
    FileNotFoundError as a 500.
    """
    if not get_docker_runner().ping():
        raise HTTPException(
            status_code=503,
            detail="Docker is not available on this CoreService host.",
        )


@plugins_router.post("/install", summary="Install a plugin from a Docker image")
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


def _parse_archive_bytes(raw: bytes):
    """Extract + validate plugin.yaml from archive bytes. Raises the
    right HTTPExceptions so callers can just propagate."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            try:
                with z.open("plugin.yaml") as f:
                    manifest_bytes = f.read()
            except KeyError:
                raise HTTPException(
                    status_code=422,
                    detail="archive has no top-level plugin.yaml — "
                           "pack with `magellon-sdk plugin pack <dir>`",
                )
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="archive is not a valid zip file")

    try:
        return load_manifest_bytes(manifest_bytes)
    except SchemaVersionError as exc:
        raise HTTPException(status_code=422, detail=f"unsupported schema_version: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface pydantic + yaml errors as-is
        raise HTTPException(status_code=422, detail=f"invalid plugin.yaml: {exc}")


def _enforce_sdk_compat(manifest) -> None:
    try:
        check_sdk_compat(manifest.sdk_compat, sdk_version)
    except SdkCompatError as exc:
        # Hard-fail: installing a plugin whose SDK pin excludes us
        # risks field-shape drift at runtime. Better the operator
        # rebuilds their plugin against a compatible SDK.
        raise HTTPException(
            status_code=409,
            detail=f"plugin incompatible with this CoreService (SDK {sdk_version}): {exc}",
        )


def _install_from_manifest(manifest) -> Dict[str, Any]:
    """Docker-run the image declared in ``manifest`` with its defaults.

    Shared by both the raw-archive upload path and the catalog-install
    path — the "spawn the container + record the install" behaviour
    is identical once we have a validated manifest in hand.
    """
    _ensure_docker()
    runner = get_docker_runner()
    volumes = [
        VolumeMount(v.host, v.container, v.read_only)
        for v in manifest.install_defaults.volumes
    ]
    entry = runner.run_image(
        image_ref=manifest.image.ref,
        env=dict(manifest.install_defaults.env),
        volumes=volumes,
        network=manifest.install_defaults.network,
    )
    if entry.state == "failed":
        get_installed_registry().add(entry)
        raise HTTPException(
            status_code=502,
            detail=f"docker run failed: {entry.error or 'unknown error'}",
        )
    get_installed_registry().add(entry)

    response = entry.to_dict()
    response["archive"] = {
        "plugin_id": manifest.plugin_id,
        "name": manifest.name,
        "version": manifest.version,
        "category": manifest.category,
    }
    return response


@plugins_router.post(
    "/install/archive",
    summary="Install a plugin from a .magplugin archive upload",
)
async def install_plugin_archive(
    archive: UploadFile = File(..., description="A .magplugin zip archive."),
) -> Dict[str, Any]:
    """Accept a ``.magplugin`` archive, validate its manifest, spawn
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


class _CatalogInstallResponse(BaseModel):
    """POST /catalog/{catalog_id}/install response shape."""
    install: Dict[str, Any]
    catalog_id: str


@plugins_router.get("/catalog", summary="Browse the plugin catalog")
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


@plugins_router.post("/catalog", summary="Upload a plugin archive to the catalog")
async def upload_catalog_entry(
    archive: UploadFile = File(..., description="A .magplugin zip archive."),
) -> Dict[str, Any]:
    """Publish a ``.magplugin`` archive to the catalog.

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


@plugins_router.delete(
    "/catalog/{catalog_id}",
    summary="Remove an entry from the catalog",
)
async def delete_catalog_entry(catalog_id: str) -> Dict[str, Any]:
    entry = get_catalog().remove(catalog_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"catalog entry {catalog_id} not found")
    return entry.to_dict()


@plugins_router.post(
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


@plugins_router.get("/installed", summary="List installed plugin containers")
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


@plugins_router.post("/installed/{install_id}/stop", summary="Stop an installed container")
async def stop_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().get(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().stop(entry)
    return entry.to_dict()


@plugins_router.delete("/installed/{install_id}", summary="Remove an installed container")
async def remove_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().remove(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().remove(entry)
    return entry.to_dict()


@plugins_router.get("/jobs", summary="List plugin jobs")
async def list_all_jobs(plugin_id: Optional[str] = None, limit: int = 100):
    return job_manager.list_jobs(plugin_id=plugin_id, limit=limit)


@plugins_router.get("/jobs/{job_id}", summary="Get plugin job detail")
async def get_any_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")


@plugins_router.delete("/jobs/{job_id}", summary="Request cancellation of a running plugin job")
async def cancel_any_job(job_id: str):
    """Cooperative cancel: flags the job so the plugin stops at its next
    progress checkpoint. Terminal jobs are untouched; the current envelope
    is returned so the caller can observe the outcome."""
    try:
        envelope = job_manager.get_job(job_id, include_result=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")

    if envelope["status"] in ("completed", "failed", "cancelled"):
        return envelope

    job_manager.request_cancel(job_id)
    return {**envelope, "cancel_requested": True}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _run_generic_job(entry, job_id: str, validated_input, sid: str | None) -> None:
    """Execute plugin.run() in a worker thread, stream progress over Socket.IO."""
    from core.socketio_server import emit_job_update, emit_log
    from plugins.progress import JobCancelledError, JobReporter

    plugin = entry.instance
    plugin_label = entry.plugin_id
    loop = asyncio.get_running_loop()
    reporter = JobReporter(job_id=job_id, sid=sid, plugin_label=plugin_label, loop=loop)

    try:
        running = job_manager.mark_running(job_id, progress=0)
        await emit_job_update(sid, running)
        await emit_log('info', plugin_label, f"{plugin_label} started (job {job_id})")

        output = await loop.run_in_executor(
            None, lambda: plugin.run(validated_input, reporter=reporter)
        )

        # Plugins return a Pydantic model; downstream code reads from dict.
        result_dict = output.model_dump() if hasattr(output, "model_dump") else output
        num_items = _infer_num_items(result_dict)

        completed = job_manager.complete_job(job_id, result=result_dict, num_items=num_items)
        await emit_job_update(sid, completed)
        await emit_log('info', plugin_label, f"{plugin_label} completed (job {job_id})")
    except JobCancelledError:
        cancelled = job_manager.cancel_job(job_id)
        await emit_job_update(sid, cancelled)
        await emit_log('info', plugin_label, f"{plugin_label} cancelled (job {job_id})")
    except Exception as exc:
        failed = job_manager.fail_job(job_id, error=str(exc))
        await emit_job_update(sid, failed)
        await emit_log('error', plugin_label, f"{plugin_label} failed: {exc}")
        logger.exception("Plugin job failed: %s", plugin_label)


def _infer_num_items(result: Any) -> int:
    """Best-effort item count — plugins expose this under different keys."""
    if not isinstance(result, dict):
        return 0
    for key in ("num_particles", "num_items", "count"):
        value = result.get(key)
        if isinstance(value, int):
            return value
    return 0

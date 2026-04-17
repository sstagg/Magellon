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
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.plugin_liveness_registry import get_registry as get_liveness_registry
from magellon_sdk.bus import get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CATEGORIES, CategoryContract
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginManifest,
    TaskDto,
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


class JobSubmitRequest(BaseModel):
    """Submit one job for a plugin. ``input`` shape is validated by the plugin."""
    input: Dict[str, Any]
    name: Optional[str] = None
    image_id: Optional[str] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None


class BatchSubmitRequest(BaseModel):
    """Fan out the same plugin over many inputs (one job per input)."""
    inputs: List[Dict[str, Any]] = Field(..., min_length=1)
    name: Optional[str] = None
    image_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None


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

    summaries: List[PluginSummary] = []
    seen_ids: set[str] = set()

    for entry in get_liveness_registry().list_live():
        plugin_id = entry.plugin_id
        if "/" not in plugin_id and entry.category:
            plugin_id = f"{entry.category}/{plugin_id}"
        if plugin_id in seen_ids:
            continue
        kind = "in-process" if plugin_id in in_process_ids else "broker"

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
    # Strip optional "category/" prefix — we only need the contract by category.
    short_id = plugin_id.split("/", 1)[1] if "/" in plugin_id else plugin_id
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id or entry.plugin_id == plugin_id:
            return _category_contract_by_name(entry.category)
    return None


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
    ``input_model`` (e.g. ``CtfTaskData``). ``PARTICLE_PICKER`` doesn't
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
) -> TaskDto:
    """Wrap a validated input in the TaskDto the bus transports.

    ``task_id`` must match the one registered with ``job_manager.create_job``;
    otherwise the step-event projector can't link events back to the
    job row and the row stays ``queued`` forever.
    """
    data = (
        validated_input.model_dump(mode="json")
        if hasattr(validated_input, "model_dump")
        else validated_input
    )
    return TaskDto(
        id=task_id,
        worker_instance_id=uuid.uuid4(),
        job_id=uuid.UUID(job_id),
        data=data,
        type=contract.category,
        status=TaskStatus(code=0, name="pending", description="Task is pending"),
    )


def _publish_to_bus(contract: CategoryContract, task: TaskDto) -> bool:
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
    # Generate the task_id up front so the same id registered with the
    # job_manager rides inside the TaskDto. The step-event projector
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
    )
    if not _publish_to_bus(contract, task):
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
        )
        if not _publish_to_bus(contract, task):
            job_manager.fail_job(env["job_id"], error="Failed to publish task to bus")
            publish_failures.append(env["job_id"])

    if publish_failures:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {len(publish_failures)}/{len(envelopes)} tasks to bus",
        )
    return {"jobs": envelopes, "count": len(envelopes)}


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

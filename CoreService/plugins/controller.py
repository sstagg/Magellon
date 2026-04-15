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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from magellon_sdk.models import Capability, IsolationLevel, PluginManifest, Transport
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
    summaries: List[PluginSummary] = []
    for entry in registry.list():
        info = entry.manifest.info
        summaries.append(PluginSummary(
            plugin_id=entry.plugin_id,
            category=entry.category,
            name=entry.name,
            version=info.version,
            schema_version=info.schema_version or "1",
            description=info.description,
            developer=info.developer,
            capabilities=list(entry.manifest.capabilities),
            supported_transports=list(entry.manifest.supported_transports),
            default_transport=entry.manifest.default_transport,
            isolation=entry.manifest.isolation,
        ))
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
    entry = _require_plugin(plugin_id)
    try:
        validated = entry.instance.input_schema().model_validate(request.input)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")

    envelope = job_manager.create_job(
        plugin_id=plugin_id,
        name=request.name or f"{entry.name} job",
        settings=validated.model_dump(mode="json"),
        image_ids=[request.image_id] if request.image_id else None,
        user_id=request.user_id,
        msession_id=request.msession_id,
    )
    asyncio.create_task(_run_generic_job(entry, envelope["job_id"], validated, sid))
    return envelope


@plugins_router.post("/{plugin_id:path}/jobs/batch", summary="Submit a batch of plugin jobs (one per input)")
async def submit_batch(plugin_id: str, request: BatchSubmitRequest, sid: str | None = None):
    entry = _require_plugin(plugin_id)

    if request.image_ids is not None and len(request.image_ids) != len(request.inputs):
        raise HTTPException(
            status_code=422,
            detail="image_ids length must match inputs length when provided",
        )

    # Validate all inputs up front — fail the whole batch cleanly rather than
    # creating half the jobs then blowing up.
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
            plugin_id=plugin_id,
            name=request.name or f"{entry.name} batch [{idx + 1}/{len(validated_inputs)}]",
            settings=validated.model_dump(mode="json"),
            image_ids=[image_id] if image_id else None,
            user_id=request.user_id,
            msession_id=request.msession_id,
        )
        envelopes.append(envelope)
        asyncio.create_task(_run_generic_job(entry, envelope["job_id"], validated, sid))

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

"""
FastAPI router for particle-picking backends.

This is the simple / direct HTTP approach — no RabbitMQ, no TaskFactory.
The existing PARTICLE_PICKING TaskCategory pipeline is untouched.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from plugins.pp.models import TemplatePickerInput, TemplatePickerOutput
from plugins.pp.template_picker.service import run_template_picker, _get_plugin

logger = logging.getLogger(__name__)

pp_router = APIRouter()

# In-memory job tracking (simple dict — sufficient for single-process)
_jobs: dict[str, dict] = {}


@pp_router.post(
    "/template-pick",
    response_model=TemplatePickerOutput,
    summary="Run template-based particle picking (synchronous)",
)
async def template_pick(input_data: TemplatePickerInput) -> TemplatePickerOutput:
    """
    Synchronous template-picking endpoint.

    Accepts a micrograph path, template paths, and picking parameters.
    Returns validated particle coordinates with scores.
    """
    try:
        return run_template_picker(input_data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Template picker failed")
        raise HTTPException(status_code=500, detail=str(exc))


@pp_router.post(
    "/template-pick-async",
    summary="Submit async template-picking job with Socket.IO progress",
)
async def template_pick_async(input_data: TemplatePickerInput, sid: str | None = None):
    """
    Submits a particle picking job that runs in the background.
    Progress is pushed via Socket.IO 'job_update' events.
    Returns a job_id immediately.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        'id': job_id,
        'name': 'Particle Picking',
        'type': 'picking',
        'status': 'queued',
        'progress': 0,
        'started_at': datetime.now().isoformat(),
        'num_particles': 0,
        'sid': sid,
    }

    asyncio.create_task(_run_picking_job(job_id, input_data, sid))

    return {'job_id': job_id, 'status': 'queued'}


async def _run_picking_job(job_id: str, input_data: TemplatePickerInput, sid: str | None):
    """Background task that runs the picker and emits progress via Socket.IO."""
    from core.socketio_server import emit_job_update, emit_log

    job = _jobs[job_id]

    try:
        # Phase 1: Starting
        job['status'] = 'running'
        job['progress'] = 10
        await emit_job_update(sid, {**job})
        await emit_log('info', 'picking', f"Particle picking started: {input_data.image_path}")

        # Phase 2: Run the actual picker in a thread (CPU-bound)
        job['progress'] = 20
        await emit_job_update(sid, {**job})
        await emit_log('info', 'picking', f"Loading micrograph and {len(input_data.template_paths)} template(s)...")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_template_picker, input_data)

        # Phase 3: Completed
        job['status'] = 'completed'
        job['progress'] = 100
        job['num_particles'] = result.num_particles
        job['result'] = result.model_dump()
        await emit_job_update(sid, {**job})
        await emit_log('info', 'picking',
                        f"Particle picking completed — {result.num_particles} particles found")

    except Exception as exc:
        job['status'] = 'failed'
        job['error'] = str(exc)
        await emit_job_update(sid, {**job})
        await emit_log('error', 'picking', f"Particle picking failed: {exc}")
        logger.exception("Async particle picking failed: %s", exc)


@pp_router.get(
    "/jobs",
    summary="List all particle picking jobs",
)
async def list_jobs():
    """Return all tracked jobs (most recent first)."""
    jobs = list(_jobs.values())
    # Don't send full result payload in listing
    return [
        {k: v for k, v in j.items() if k != 'result'}
        for j in reversed(jobs)
    ]


@pp_router.get(
    "/jobs/{job_id}",
    summary="Get particle picking job details",
)
async def get_job(job_id: str):
    """Return a specific job including its result if completed."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


@pp_router.get(
    "/template-pick/info",
    summary="Template picker plugin metadata",
)
async def template_pick_info():
    plugin = _get_plugin()
    return plugin.get_info()


@pp_router.get(
    "/template-pick/health",
    summary="Template picker health check",
)
async def template_pick_health():
    plugin = _get_plugin()
    return plugin.health_check()


@pp_router.get(
    "/template-pick/requirements",
    summary="Template picker dependency check",
)
async def template_pick_requirements():
    plugin = _get_plugin()
    return plugin.check_requirements()


@pp_router.get(
    "/template-pick/schema/input",
    summary="Template picker input JSON schema",
)
async def template_pick_input_schema():
    return TemplatePickerInput.model_json_schema()


@pp_router.get(
    "/template-pick/schema/output",
    summary="Template picker output JSON schema",
)
async def template_pick_output_schema():
    return TemplatePickerOutput.model_json_schema()

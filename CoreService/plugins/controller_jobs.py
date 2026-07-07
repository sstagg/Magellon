"""Async-job routes for the plugins router.

Submit (single / batch) plus the job list / detail / cancel surface.
Dispatch mechanics live in :mod:`plugins.dispatch_service`.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from services.job_manager import job_manager

from plugins.dispatch_service import _submit_broker_batch, _submit_broker_job
from plugins.registry_service import _find_broker_plugin
from plugins.schemas import BatchSubmitRequest, JobSubmitRequest

jobs_router = APIRouter()


# ---------------------------------------------------------------------------
# Job submission — single and batch
# ---------------------------------------------------------------------------

@jobs_router.post("/{plugin_id:path}/jobs", summary="Submit one plugin job (async)")
async def submit_job(plugin_id: str, request: JobSubmitRequest, sid: str | None = None):
    """Dispatch one job to a broker plugin via ``bus.tasks.send``.

    Post-PI-6 there are no in-process plugins; every dispatch flows
    through the bus. The plugin's runner consumes the task and
    publishes the result + step events back. ``job_manager`` rows
    track lifecycle the same way regardless of where the plugin runs.
    """
    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_job(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@jobs_router.post("/{plugin_id:path}/jobs/batch", summary="Submit a batch of plugin jobs (one per input)")
async def submit_batch(plugin_id: str, request: BatchSubmitRequest, sid: str | None = None):
    if request.image_ids is not None and len(request.image_ids) != len(request.inputs):
        raise HTTPException(
            status_code=422,
            detail="image_ids length must match inputs length when provided",
        )

    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_batch(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@jobs_router.get("/jobs", summary="List plugin jobs")
async def list_all_jobs(plugin_id: Optional[str] = None, limit: int = 100):
    return job_manager.list_jobs(plugin_id=plugin_id, limit=limit)


@jobs_router.get("/jobs/{job_id}", summary="Get plugin job detail")
async def get_any_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")


@jobs_router.delete("/jobs/{job_id}", summary="Request cancellation of a running plugin job")
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

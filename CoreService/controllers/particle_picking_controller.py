"""Particle-picking HTTP surface (PI-4).

Lifts the routes that used to live at ``/plugins/pp/template-pick/*``
into ``/particle-picking/*``. Per the PI-4 plan, these aren't really
"plugin" endpoints — preview, retune, run-and-save, batch, COCO,
session-images are particle-picking *features* that happen to be
implemented via template matching today. Putting them at a feature-
named URL (rather than a plugin-id-shaped URL) lets us swap the
underlying impl without breaking the wire shape.

Implementation: this controller does not duplicate the handler
bodies — it imports the existing handler functions from
``plugins.pp.controller`` and re-registers them on a new router
under cleaner paths. PI-5 will move those handlers (and the
underlying compute) out of ``plugins/pp/`` once nothing else
references the old location; this controller's imports flip to the
new location at that time.

URL map (old → new):

  POST   /plugins/pp/template-pick                    → POST   /particle-picking/
  POST   /plugins/pp/template-pick/preview            → POST   /particle-picking/preview
  POST   /plugins/pp/template-pick/preview/{id}/retune → POST   /particle-picking/preview/{id}/retune
  DELETE /plugins/pp/template-pick/preview/{id}       → DELETE /particle-picking/preview/{id}
  POST   /plugins/pp/template-pick-async              → POST   /particle-picking/async
  GET    /plugins/pp/jobs                             → GET    /particle-picking/jobs
  GET    /plugins/pp/jobs/{job_id}                    → GET    /particle-picking/jobs/{job_id}
  GET    /plugins/pp/template-pick/info               → GET    /particle-picking/info
  GET    /plugins/pp/template-pick/health             → GET    /particle-picking/health
  GET    /plugins/pp/template-pick/requirements       → GET    /particle-picking/requirements
  GET    /plugins/pp/template-pick/schema/input       → GET    /particle-picking/schema/input
  GET    /plugins/pp/template-pick/schema/output      → GET    /particle-picking/schema/output
  GET    /plugins/pp/template-pick/session-images     → GET    /particle-picking/session-images
  POST   /plugins/pp/template-pick/run-and-save       → POST   /particle-picking/run-and-save
  POST   /plugins/pp/template-pick/batch              → POST   /particle-picking/batch
  GET    /plugins/pp/template-pick/records/{oid}/coco → GET    /particle-picking/records/{oid}/coco

Both surfaces stay live until PI-5 unmounts the legacy ``pp_router``.
"""
from __future__ import annotations

from fastapi import APIRouter

from plugins.pp.controller import (
    RunAndSaveResponse,
    get_job,
    list_jobs,
    list_session_images,
    template_pick,
    template_pick_async,
    template_pick_batch,
    template_pick_health,
    template_pick_info,
    template_pick_input_schema,
    template_pick_output_schema,
    template_pick_preview,
    template_pick_preview_delete,
    template_pick_record_coco,
    template_pick_requirements,
    template_pick_retune,
    template_pick_run_and_save,
)
from plugins.pp.models import (
    PreviewResult,
    RetuneResult,
    TemplatePickerOutput,
)

particle_picking_router = APIRouter()


# Synchronous run.
particle_picking_router.add_api_route(
    "/",
    template_pick,
    methods=["POST"],
    response_model=TemplatePickerOutput,
    summary="Run template-based particle picking (synchronous)",
)

# Preview / retune flow.
particle_picking_router.add_api_route(
    "/preview",
    template_pick_preview,
    methods=["POST"],
    response_model=PreviewResult,
    summary="Compute correlation maps and return initial picks + score map",
)
particle_picking_router.add_api_route(
    "/preview/{preview_id}/retune",
    template_pick_retune,
    methods=["POST"],
    response_model=RetuneResult,
    summary="Re-extract particles with new tunable params (no recompute)",
)
particle_picking_router.add_api_route(
    "/preview/{preview_id}",
    template_pick_preview_delete,
    methods=["DELETE"],
    summary="Discard a preview and free memory",
)

# Async job submission + listing.
particle_picking_router.add_api_route(
    "/async",
    template_pick_async,
    methods=["POST"],
    summary="Submit async template-picking job with Socket.IO progress",
)
particle_picking_router.add_api_route(
    "/jobs",
    list_jobs,
    methods=["GET"],
    summary="List particle-picking jobs",
)
particle_picking_router.add_api_route(
    "/jobs/{job_id}",
    get_job,
    methods=["GET"],
    summary="Get particle-picking job details",
)

# Plugin metadata (kept here for back-compat with the old paths).
particle_picking_router.add_api_route(
    "/info",
    template_pick_info,
    methods=["GET"],
    summary="Template picker plugin metadata",
)
particle_picking_router.add_api_route(
    "/health",
    template_pick_health,
    methods=["GET"],
    summary="Template picker health check",
)
particle_picking_router.add_api_route(
    "/requirements",
    template_pick_requirements,
    methods=["GET"],
    summary="Template picker dependency check",
)
particle_picking_router.add_api_route(
    "/schema/input",
    template_pick_input_schema,
    methods=["GET"],
    summary="Template picker input JSON schema",
)
particle_picking_router.add_api_route(
    "/schema/output",
    template_pick_output_schema,
    methods=["GET"],
    summary="Template picker output JSON schema",
)

# Session-images browse + run-and-save + batch — the feature-level routes.
particle_picking_router.add_api_route(
    "/session-images",
    list_session_images,
    methods=["GET"],
    summary="List images in a session filtered by magnification",
)
particle_picking_router.add_api_route(
    "/run-and-save",
    template_pick_run_and_save,
    methods=["POST"],
    response_model=RunAndSaveResponse,
    summary="Run template-picking on one session image and persist the result",
)
particle_picking_router.add_api_route(
    "/batch",
    template_pick_batch,
    methods=["POST"],
    summary="Run template-picking on a list of session images (async)",
)
particle_picking_router.add_api_route(
    "/records/{ipp_oid}/coco",
    template_pick_record_coco,
    methods=["GET"],
    summary="Export a particle-picking record as a COCO annotations JSON",
)


__all__ = ["particle_picking_router"]

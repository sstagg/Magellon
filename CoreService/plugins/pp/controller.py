"""
FastAPI router for particle-picking backends.

This is the simple / direct HTTP approach — no RabbitMQ, no TaskFactory.
The existing PARTICLE_PICKING TaskCategory pipeline is untouched.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from plugins.pp.models import TemplatePickerInput, TemplatePickerOutput
from plugins.pp.template_picker.service import run_template_picker, _get_plugin

logger = logging.getLogger(__name__)

pp_router = APIRouter()


@pp_router.post(
    "/template-pick",
    response_model=TemplatePickerOutput,
    summary="Run template-based particle picking",
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

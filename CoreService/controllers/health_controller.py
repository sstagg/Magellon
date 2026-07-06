"""Process health endpoints for deployment probes and operators."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Request
from sqlalchemy import text
from starlette.responses import JSONResponse

from database import session_local

health_router = APIRouter()


def _check_database() -> Tuple[bool, Dict[str, Any]]:
    try:
        with session_local() as db:
            db.execute(text("SELECT 1"))
        return True, {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return False, {"status": "error", "error": str(exc)}


def _check_bus() -> Tuple[bool, Dict[str, Any]]:
    try:
        from magellon_sdk.bus import get_bus

        bus = get_bus()
        return True, {"status": "ok", "type": type(bus).__name__}
    except Exception as exc:  # noqa: BLE001
        return False, {"status": "error", "error": str(exc)}


def _state_service(request: Request, attr: str, enabled_env: str, default_enabled: str = "1") -> Dict[str, Any]:
    enabled = os.environ.get(enabled_env, default_enabled) != "0"
    service = getattr(request.app.state, attr, None)
    if not enabled:
        return {"status": "disabled"}
    if service is None:
        return {"status": "degraded", "error": "not started"}
    return {"status": "ok", "type": type(service).__name__}


@health_router.get("/live", include_in_schema=False)
def live() -> Dict[str, Any]:
    return {"status": "ok", "service": "magellon-core", "checked_at": time.time()}


@health_router.get("/ready", include_in_schema=False)
def ready(request: Request) -> JSONResponse:
    db_ok, db_check = _check_database()
    bus_ok, bus_check = _check_bus()
    checks = {
        "database": db_check,
        "message_bus": bus_check,
        "rmq_step_event_forwarder": _state_service(
            request, "rmq_step_event_forwarder", "MAGELLON_RMQ_STEP_EVENTS_FORWARDER"
        ),
        "nats_step_event_forwarder": _state_service(
            request, "step_event_forwarder", "MAGELLON_STEP_EVENTS_FORWARDER"
        ),
        "plugin_liveness_listener": _state_service(
            request, "plugin_liveness_listener", "MAGELLON_PLUGIN_LIVENESS_LISTENER"
        ),
        "operational_event_logger": _state_service(
            request, "operational_event_logger", "MAGELLON_OPERATIONAL_EVENT_LOGGER"
        ),
    }

    ok = db_ok and bus_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not_ready",
            "service": "magellon-core",
            "checked_at": time.time(),
            "checks": checks,
        },
    )


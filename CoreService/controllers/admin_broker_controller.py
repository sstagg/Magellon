"""Broker health HTTP surface — backs the Pipeline Health page.

One endpoint, intentionally narrow: ``GET /admin/broker/health``.
Anything broader (per-queue browse, message inspection, publish/purge)
should defer to the built-in RabbitMQ Management UI on :15672 — we're
not reinventing it.

Wide-open authz today (no role requirement) so the page works during
local dev without a token. Tighten to ``require_role("Administrator")``
once the page goes behind login in production.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from config import app_settings
from services import broker_inspector_service

logger = logging.getLogger(__name__)

admin_broker_router = APIRouter()


@admin_broker_router.get(
    "/health",
    summary="Magellon-domain projection of RMQ state + plugin liveness",
)
def get_broker_health() -> dict:
    # Plain `def` (not async) so FastAPI runs this on the threadpool.
    # The service does a blocking urllib call to the RMQ Management API;
    # an `async def` here would stall the entire event loop (and every
    # websocket reconnect with it) for up to _HTTP_TIMEOUT_S per request.
    return broker_inspector_service.get_broker_health(app_settings.rabbitmq_settings)


__all__ = ["admin_broker_router"]

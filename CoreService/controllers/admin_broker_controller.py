"""Broker inspection HTTP surface — backs the Pipeline Health page.

Three endpoints, narrow on purpose:

  * ``GET  /admin/broker/health`` — Magellon-domain projection of broker
    state + plugin liveness. Open access (page renders during local dev
    without a token).

  * ``GET  /admin/broker/queues/{name}/peek?count=N`` — read-only message
    inspection via auto-requeue. Administrator only — peek perturbs queue
    ordering and exposes payload contents.

  * ``POST /admin/broker/queues/{name}/purge`` — drop every pending
    message in the queue. Administrator only, irreversible.

For broader operations (per-vhost browse, message publish, exchange
binding edits) defer to the built-in RabbitMQ Management UI on :15672 —
we're not reinventing it.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from config import app_settings
from dependencies.permissions import require_role
from services import broker_inspector_service, cancellation_service

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


@admin_broker_router.get(
    "/queues/{name}/peek",
    summary="Peek up to N messages from a queue (auto-requeue)",
)
def peek_queue(
    name: str,
    count: int = Query(10, ge=1, le=50),
    _: None = Depends(require_role("Administrator")),
) -> dict:
    return broker_inspector_service.peek_queue(
        app_settings.rabbitmq_settings, name, count=count,
    )


@admin_broker_router.post(
    "/queues/{name}/purge",
    summary="Drop every pending message in a queue (irreversible)",
)
def purge_queue(
    name: str,
    _: None = Depends(require_role("Administrator")),
) -> dict:
    try:
        purged = cancellation_service.purge_queue(app_settings.rabbitmq_settings, name)
    except Exception as exc:  # noqa: BLE001 — surface to UI verbatim
        logger.exception("purge_queue failed: %s", name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info("purge_queue: %s drained %d messages", name, purged)
    return {"queue": name, "purged": purged}


__all__ = ["admin_broker_router"]

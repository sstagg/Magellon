"""Cancellation HTTP surface (P9).

Two operator levers, mirroring the two primitives in
:mod:`services.cancellation_service`:

  - ``POST /cancellation/queues/purge`` — drain pending tasks from one
    or more category queues. Pending = the broker still has them; the
    plugin hasn't pulled them off yet. Returns ``{queue: count}`` so
    the operator sees what was thrown away.

  - ``POST /cancellation/containers/{container_name}/kill`` — docker
    kill a plugin replica that's stuck mid-execute. Pairs with the
    purge above: queue-purge alone won't help once a long-running
    delivery is already in the plugin's hands.

The controller stays thin — authz check, request logging, dispatch,
echo the service result. All broker / docker work lives in the
service module so unit tests can mock the boundary cleanly.

There is intentionally no ``cancel by job_id`` endpoint here: AMQP
has no notion of "cancel one delivery" and we don't track per-task
container ids. Cooperative cancellation (the JobManager flag plugins
poll at stage boundaries) covers that case in
``services.job_manager.request_cancel``; this controller is the
hard-stop path operators reach for when cooperative cancel won't do.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import app_settings
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role
from services import cancellation_service

logger = logging.getLogger(__name__)

cancellation_router = APIRouter()


class PurgeQueuesRequest(BaseModel):
    """Bulk-purge body. One or more queue names; partial success is
    fine — an unknown queue is reported as ``-1`` rather than 4xx so
    a single typo doesn't block the others."""
    queue_names: List[str] = Field(..., min_length=1)


class PurgeQueuesResponse(BaseModel):
    purged: dict[str, int]


class KillContainerResponse(BaseModel):
    container_name: str
    id: str
    signal: str
    status: str


@cancellation_router.post(
    "/queues/purge",
    response_model=PurgeQueuesResponse,
    summary="Drain pending tasks from one or more category queues",
)
async def purge_queues(
    request: PurgeQueuesRequest,
    _: None = Depends(require_role("Administrator")),
    user_id: UUID = Depends(get_current_user_id),
) -> PurgeQueuesResponse:
    logger.info(
        "cancellation: purge_queues requested by user=%s queues=%s",
        user_id, request.queue_names,
    )
    try:
        purged = cancellation_service.purge_queues(
            app_settings.rabbitmq_settings, request.queue_names
        )
    except Exception as exc:
        # Connection-level failure (broker unreachable) — partial
        # failures inside purge_queues are already swallowed to -1.
        logger.exception("cancellation: purge_queues broker error")
        raise HTTPException(status_code=502, detail=f"broker error: {exc}") from exc

    return PurgeQueuesResponse(purged=purged)


@cancellation_router.post(
    "/containers/{container_name}/kill",
    response_model=KillContainerResponse,
    summary="docker kill a plugin replica by container name",
)
async def kill_container(
    container_name: str,
    signal: str = "SIGKILL",
    _: None = Depends(require_role("Administrator")),
    user_id: UUID = Depends(get_current_user_id),
) -> KillContainerResponse:
    logger.info(
        "cancellation: kill_container requested by user=%s name=%s signal=%s",
        user_id, container_name, signal,
    )
    try:
        result = cancellation_service.kill_plugin_container(
            container_name, signal=signal
        )
    except Exception as exc:
        # docker SDK raises NotFound / APIError; surface as 404 / 502
        # rather than the generic 500 the global handler would emit.
        msg = str(exc)
        status = 404 if "not found" in msg.lower() or "no such container" in msg.lower() else 502
        logger.warning("cancellation: kill_container failed: %s", msg)
        raise HTTPException(status_code=status, detail=msg) from exc

    return KillContainerResponse(**result)


__all__ = ["cancellation_router"]

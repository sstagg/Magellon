"""Admin endpoint for the PE2 dispatch cache.

One verb: ``POST /admin/dispatch-cache/invalidate`` to soft-delete
cache rows matching a filter. Filters are optional but at least one
must be supplied — an unfiltered call is refused as a safety check
(see :func:`services.dispatch_cache.invalidate_cache`).

The cache itself populates via ``TaskOutputProcessor._maybe_write_artifact``
and is consulted by ``_try_dispatch_cache_hit`` in
``plugins/controller.py``. Invalidation is the "manual hard reset"
arm of the plan's three invalidation cases — version-bump invalidation
and superseded-input invalidation happen automatically (per the cache
service's docstring).
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies.permissions import require_role
from services.dispatch_cache import invalidate_cache

logger = logging.getLogger(__name__)

admin_dispatch_cache_router = APIRouter()


class InvalidateRequest(BaseModel):
    """Filter for the invalidation. At least one field must be set."""

    plugin_id: Optional[str] = Field(
        None,
        description="Producer plugin slug (e.g. 'stack-maker'). Matches the "
                    "value the writer stamps onto Artifact.producer_plugin_id.",
    )
    plugin_version: Optional[str] = Field(
        None,
        description="Producer version. Combine with plugin_id to invalidate "
                    "just one release; on its own to nuke a version across "
                    "every plugin.",
    )
    artifact_oid: Optional[UUID] = Field(
        None,
        description="Single artifact to invalidate. Used when one bad run "
                    "needs a targeted clear without affecting siblings.",
    )


class InvalidateResponse(BaseModel):
    invalidated: int
    """Number of artifact rows soft-deleted (deleted_at set to now())."""


@admin_dispatch_cache_router.post(
    "/invalidate",
    response_model=InvalidateResponse,
    summary="Soft-delete cache-eligible Artifact rows matching a filter",
)
def invalidate(
    body: InvalidateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("Administrator")),
) -> InvalidateResponse:
    """Mark matching artifact rows as superseded so future dispatch
    cache lookups miss and run fresh.

    Refuses the no-filter case (returns 400) — set at least one of
    ``plugin_id``, ``plugin_version``, ``artifact_oid``.
    """
    if (
        body.plugin_id is None
        and body.plugin_version is None
        and body.artifact_oid is None
    ):
        raise HTTPException(
            status_code=400,
            detail="At least one filter required: plugin_id, plugin_version, "
                   "or artifact_oid.",
        )

    count = invalidate_cache(
        db,
        plugin_id=body.plugin_id,
        plugin_version=body.plugin_version,
        artifact_oid=body.artifact_oid,
    )
    return InvalidateResponse(invalidated=count)


__all__ = ["admin_dispatch_cache_router"]

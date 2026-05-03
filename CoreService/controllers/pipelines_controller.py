"""HTTP endpoints for PipelineRun (Phase 8b, 2026-05-03).

A PipelineRun rolls up a sequence of ImageJobs (each algorithm step
— motioncor, ctf, picker, extraction, classification — is its own
job per the architecture review). These endpoints let an operator
or UI create / list / inspect / soft-delete the rollup row; the
child ImageJobs link via ``ImageJob.parent_run_id``.

Endpoints:

    POST   /pipelines/runs          create
    GET    /pipelines/runs/{oid}    detail (with child jobs summary)
    GET    /pipelines/runs          list (optional msession_id filter)
    DELETE /pipelines/runs/{oid}    soft-delete (sets deleted_at)

Authoritative writes for ``status_id`` / ``started_date`` /
``ended_date`` happen elsewhere — those flip when child jobs
transition. This controller deliberately doesn't expose a PUT for
the run row itself (rule 6: artifacts / runs are immutable post-
creation; the only mutation is soft-delete).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission
from models.pydantic_pipelines_models import (
    PipelineRunCreate,
    PipelineRunDetail,
    PipelineRunJobSummary,
    PipelineRunSummary,
)
from models.sqlalchemy_models import ImageJob, PipelineRun

logger = logging.getLogger(__name__)
pipelines_router = APIRouter()


# ---------------------------------------------------------------------------
# Status enum — mirrors ImageJob convention
# ---------------------------------------------------------------------------

_STATUS_PENDING = 1
_STATUS_RUNNING = 2
_STATUS_COMPLETED = 4
_STATUS_FAILED = 5
_STATUS_CANCELLED = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_summary(run: PipelineRun, *, job_count: int = 0) -> PipelineRunSummary:
    return PipelineRunSummary(
        oid=run.oid,
        name=run.name,
        msession_id=run.msession_id,
        status_id=run.status_id,
        created_date=run.created_date,
        started_date=run.started_date,
        ended_date=run.ended_date,
        job_count=job_count,
    )


def _to_detail(run: PipelineRun, jobs: List[ImageJob]) -> PipelineRunDetail:
    return PipelineRunDetail(
        oid=run.oid,
        name=run.name,
        description=run.description,
        msession_id=run.msession_id,
        status_id=run.status_id,
        created_date=run.created_date,
        started_date=run.started_date,
        ended_date=run.ended_date,
        settings=run.settings,
        user_id=run.user_id,
        deleted_at=run.deleted_at,
        jobs=[
            PipelineRunJobSummary(
                oid=j.oid,
                name=j.name,
                status_id=j.status_id,
                type_id=j.type_id,
                plugin_id=j.plugin_id,
                created_date=j.created_date,
                start_date=j.start_date,
                end_date=j.end_date,
            )
            for j in jobs
        ],
    )


# ---------------------------------------------------------------------------
# POST — create
# ---------------------------------------------------------------------------

@pipelines_router.post("/runs", response_model=PipelineRunDetail, status_code=201)
async def create_pipeline_run(
    payload: PipelineRunCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission("pipeline_run", "create")),
    user_id: UUID = Depends(get_current_user_id),
):
    """Create a new PipelineRun. Status starts at 1 (pending). Child
    ImageJobs are linked separately via ``ImageJob.parent_run_id`` —
    this endpoint just creates the rollup row."""
    logger.info("User %s creating pipeline run: %s", user_id, payload.name)

    if not (payload.name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name is required",
        )

    run = PipelineRun(
        oid=uuid.uuid4(),
        name=payload.name.strip(),
        description=payload.description,
        msession_id=payload.msession_id,
        status_id=_STATUS_PENDING,
        created_date=datetime.utcnow(),
        settings=payload.settings,
        user_id=str(user_id) if user_id else None,
    )
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
    except Exception:
        db.rollback()
        logger.exception("create_pipeline_run failed for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create pipeline run",
        )

    return _to_detail(run, jobs=[])


# ---------------------------------------------------------------------------
# GET — detail (with child jobs summary)
# ---------------------------------------------------------------------------

@pipelines_router.get("/runs/{oid}", response_model=PipelineRunDetail)
def get_pipeline_run(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Detail view + child jobs. Soft-deleted runs return 404 to keep
    the "deleted means gone" UX; pass ``include_deleted=true`` to
    raw-list via the list endpoint if needed for audit."""
    run = db.query(PipelineRun).filter(PipelineRun.oid == oid).first()
    if run is None or run.deleted_at is not None:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    jobs = (
        db.query(ImageJob)
        .filter(ImageJob.parent_run_id == oid)
        .order_by(ImageJob.created_date.asc())
        .all()
    )
    return _to_detail(run, jobs=jobs)


# ---------------------------------------------------------------------------
# GET — list
# ---------------------------------------------------------------------------

@pipelines_router.get("/runs", response_model=List[PipelineRunSummary])
def list_pipeline_runs(
    msession_id: Optional[str] = Query(None, description="Filter by session"),
    include_deleted: bool = Query(False, description="Include soft-deleted runs"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """List PipelineRuns, newest first. Filters by session when set;
    excludes soft-deleted unless ``include_deleted=true``."""
    q = db.query(PipelineRun)
    if msession_id:
        q = q.filter(PipelineRun.msession_id == msession_id)
    if not include_deleted:
        q = q.filter(PipelineRun.deleted_at.is_(None))
    runs = q.order_by(PipelineRun.created_date.desc()).limit(limit).all()
    if not runs:
        return []

    # Pull child-job counts in one query rather than N+1.
    run_oids = [r.oid for r in runs]
    counts: dict = {}
    rows = (
        db.query(ImageJob.parent_run_id, ImageJob.oid)
        .filter(ImageJob.parent_run_id.in_(run_oids))
        .all()
    )
    for parent, _job_oid in rows:
        counts[parent] = counts.get(parent, 0) + 1

    return [_to_summary(r, job_count=counts.get(r.oid, 0)) for r in runs]


# ---------------------------------------------------------------------------
# DELETE — soft-delete
# ---------------------------------------------------------------------------

@pipelines_router.delete("/runs/{oid}")
async def delete_pipeline_run(
    oid: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission("pipeline_run", "delete")),
    user_id: UUID = Depends(get_current_user_id),
):
    """Soft-delete only — sets ``deleted_at``. Hard-delete is
    forbidden because child ImageJobs reference parent_run_id; we
    don't want to break lineage queries.
    """
    run = db.query(PipelineRun).filter(PipelineRun.oid == oid).first()
    if run is None:
        raise HTTPException(status_code=404, detail="PipelineRun not found")
    if run.deleted_at is not None:
        return {"message": "PipelineRun already deleted", "oid": str(oid)}

    run.deleted_at = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("delete_pipeline_run failed for %s", oid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete pipeline run",
        )
    logger.info("PipelineRun %s soft-deleted by user %s", oid, user_id)
    return {"message": "PipelineRun soft-deleted", "oid": str(oid)}

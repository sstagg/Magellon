"""HTTP read surface for the Artifact entity (Medium #7, 2026-05-04 fix).

Phase 4 (5fb2af0) added the artifact table; Phase 5b/7b
(11f5465 / f8e84fa) wired TaskOutputProcessor to write
``particle_stack`` and ``class_averages`` rows. Without this
controller, the UI / downstream orchestration can't resolve
``particle_stack_id`` over HTTP — they'd have to query the DB
directly, which breaks the layering principle.

Endpoints:

    GET /artifacts/{oid}                              detail
    GET /artifacts                                    list (filter by
                                                      msession_id, kind,
                                                      producing_job_id,
                                                      source_artifact_id)
    GET /artifacts/{oid}/lineage                      ancestors + descendants

Per ratified rule 6 (artifact immutability) there are no PUT/PATCH
endpoints. DELETE is intentionally absent — soft-delete is owned by
the producing job's lifecycle, not by ad-hoc HTTP calls.

Per rule 1 (refs only on bus): the response carries paths
(``mrcs_path``, ``star_path``) for downstream consumers to resolve;
this controller does NOT serve file content. Use a separate file
endpoint when bytes are needed.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user_id
from models.sqlalchemy_models import Artifact

logger = logging.getLogger(__name__)
artifacts_router = APIRouter()


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class ArtifactView(BaseModel):
    """Canonical wire shape for the Artifact row."""

    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    kind: str
    producing_job_id: Optional[UUID] = None
    producing_task_id: Optional[UUID] = None
    msession_id: Optional[str] = None
    source_artifact_id: Optional[UUID] = None
    mrcs_path: Optional[str] = None
    star_path: Optional[str] = None
    particle_count: Optional[int] = None
    apix: Optional[float] = None
    box_size: Optional[int] = None
    data_json: Optional[Dict[str, Any]] = None
    created_date: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class ArtifactLineageView(BaseModel):
    """Ancestors + descendants graph rooted at one artifact.

    ``ancestors`` walks ``source_artifact_id`` upward (most-recent
    first). ``descendants`` finds rows whose ``source_artifact_id``
    points at this row.
    """

    artifact: ArtifactView
    ancestors: List[ArtifactView]
    descendants: List[ArtifactView]


# ---------------------------------------------------------------------------
# GET /artifacts/{oid} — detail
# ---------------------------------------------------------------------------


@artifacts_router.get("/{oid}", response_model=ArtifactView)
def get_artifact(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Detail view. Soft-deleted rows return 404 (consistent with the
    PipelineRun controller's UX — deleted means gone)."""
    row = db.query(Artifact).filter(Artifact.oid == oid).first()
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return row


# ---------------------------------------------------------------------------
# GET /artifacts — list with filters
# ---------------------------------------------------------------------------


@artifacts_router.get("", response_model=List[ArtifactView])
def list_artifacts(
    msession_id: Optional[str] = Query(None, description="Filter by session"),
    kind: Optional[str] = Query(None, description="e.g. particle_stack | class_averages"),
    producing_job_id: Optional[UUID] = Query(None),
    source_artifact_id: Optional[UUID] = Query(
        None,
        description="Find artifacts derived from this one — e.g. all "
                    "classifications of a given particle_stack.",
    ),
    include_deleted: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """List artifacts, newest-first. ``source_artifact_id`` is the
    canonical "all classifications of stack X" query — pre-Phase-7
    fix this required a JSON-contains scan on data_json. Now it's a
    simple FK index lookup (alembic 0007)."""
    q = db.query(Artifact)
    if msession_id:
        q = q.filter(Artifact.msession_id == msession_id)
    if kind:
        q = q.filter(Artifact.kind == kind)
    if producing_job_id:
        q = q.filter(Artifact.producing_job_id == producing_job_id)
    if source_artifact_id:
        q = q.filter(Artifact.source_artifact_id == source_artifact_id)
    if not include_deleted:
        q = q.filter(Artifact.deleted_at.is_(None))
    return q.order_by(Artifact.created_date.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# GET /artifacts/{oid}/lineage — ancestors + descendants
# ---------------------------------------------------------------------------


@artifacts_router.get("/{oid}/lineage", response_model=ArtifactLineageView)
def get_artifact_lineage(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Walk the ``source_artifact_id`` graph in both directions.

    Ancestors: this row → its source → its source's source → ...
    Descendants: every row whose ``source_artifact_id`` points at
    this one (depth=1; deeper recursion is a follow-up).
    """
    root = db.query(Artifact).filter(Artifact.oid == oid).first()
    if root is None or root.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Ancestors — bounded walk to avoid pathological cycles. Cycles
    # shouldn't happen (immutability + monotonic created_date) but
    # the bound is cheap insurance.
    ancestors: List[Artifact] = []
    seen: set = {root.oid}
    cursor = root.source_artifact_id
    for _ in range(20):
        if cursor is None or cursor in seen:
            break
        seen.add(cursor)
        parent = db.query(Artifact).filter(Artifact.oid == cursor).first()
        if parent is None:
            break
        ancestors.append(parent)
        cursor = parent.source_artifact_id

    # Descendants — direct children only for now. Deeper recursion is
    # a follow-up if a UI driver needs the full subtree.
    descendants = (
        db.query(Artifact)
        .filter(Artifact.source_artifact_id == oid)
        .filter(Artifact.deleted_at.is_(None))
        .order_by(Artifact.created_date.desc())
        .all()
    )

    return ArtifactLineageView(
        artifact=ArtifactView.model_validate(root, from_attributes=True),
        ancestors=[ArtifactView.model_validate(a, from_attributes=True) for a in ancestors],
        descendants=[ArtifactView.model_validate(d, from_attributes=True) for d in descendants],
    )

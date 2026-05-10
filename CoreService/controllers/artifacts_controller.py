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
    GET /artifacts/{oid}/workflow.json                PE3-lite: portable
                                                      provenance dump

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
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user_id
from models.sqlalchemy_models import Artifact, ImageJobTask

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
# PE3-lite (2026-05-10): workflow.json — portable provenance export
# ---------------------------------------------------------------------------
#
# A serializer over the single-parent ancestor chain that names enough
# producer metadata for a user (or a future replay tool) to reconstruct
# how an artifact came to exist. NOT a graph: today
# ``Artifact.source_artifact_id`` is a single-parent FK, so the export
# advertises ``lineage_shape='single_parent_chain'``. When true
# multi-input DAG lineage lands, the value flips to ``'dag'`` and
# ``ancestors`` grows edges.


_WORKFLOW_LINEAGE_DEPTH = 200
"""Cap on chain depth for the workflow.json walk. The existing
/lineage endpoint uses 20 for UI display; export tolerates more
because offline tools want the full chain when possible. Truncation
sets ``truncated_at_depth`` so consumers know they got a prefix."""


_SECRET_KEY_RE = re.compile(r"(secret|password|token|api[_-]?key)", re.IGNORECASE)
"""Heuristic redaction. Manifest-driven ``params.<key>.export: false``
is the right long-term answer (see PIPELINE_ERGONOMICS_PLAN.md PE3
§3.2); the regex covers the common cases without that contract."""


class WorkflowProducer(BaseModel):
    """The plugin invocation that produced an artifact in the chain."""

    plugin_id: Optional[str] = None
    plugin_version: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    """Task settings (``ImageJobTask.data_json``). Secret-keyed values
    are redacted to ``'<redacted>'`` — see ``_SECRET_KEY_RE``."""


class WorkflowNode(BaseModel):
    """One artifact in the lineage chain. ``producer`` is ``None`` for
    imported / top-of-pipeline artifacts (those with no
    ``producing_task_id``)."""

    oid: UUID
    kind: str
    msession_id: Optional[str] = None
    created_date: Optional[datetime] = None
    producer: Optional[WorkflowProducer] = None


class WorkflowExport(BaseModel):
    """Portable provenance dump. Embeddable in exported files (sidecar
    JSON, PNG ``tEXt``, star header comments) so users can answer "how
    did this come to exist?" without DB access.
    """

    magellon_workflow_version: int = 1
    exported_at: datetime
    lineage_shape: str
    """Literal ``'single_parent_chain'`` today; flips to ``'dag'`` when
    multi-input lineage lands."""
    root_artifact: WorkflowNode
    ancestors: List[WorkflowNode]
    truncated_at_depth: Optional[int] = None


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


# ---------------------------------------------------------------------------
# GET /artifacts/{oid}/workflow.json — PE3-lite portable provenance
# ---------------------------------------------------------------------------


def _redact_secrets(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Shallow redaction of secret-keyed values. See ``_SECRET_KEY_RE``."""
    if not params:
        return params
    return {
        k: ("<redacted>" if _SECRET_KEY_RE.search(k) else v)
        for k, v in params.items()
    }


def _artifact_to_workflow_node(db: Session, art: Artifact) -> WorkflowNode:
    """Build the producer block by joining ``artifact → producing_task``.

    Imported / top-of-pipeline artifacts have no producing_task — their
    ``producer`` field is ``None``. The endpoint contract is "honest
    representation of what the DB records," so we don't synthesize a
    producer for rows where none exists.
    """
    producer: Optional[WorkflowProducer] = None
    if art.producing_task_id is not None:
        task = (
            db.query(ImageJobTask)
            .filter(ImageJobTask.oid == art.producing_task_id)
            .first()
        )
        if task is not None:
            producer = WorkflowProducer(
                plugin_id=task.plugin_id,
                plugin_version=task.plugin_version,
                params=_redact_secrets(task.data_json),
            )
    return WorkflowNode(
        oid=art.oid,
        kind=art.kind,
        msession_id=art.msession_id,
        created_date=art.created_date,
        producer=producer,
    )


@artifacts_router.get("/{oid}/workflow.json", response_model=WorkflowExport)
def get_artifact_workflow(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """PE3-lite: serialize the single-parent ancestor chain + producer
    plugin metadata as a portable JSON document.

    Honest about today's lineage shape:
    ``Artifact.source_artifact_id`` is a single parent FK, so the
    export advertises ``lineage_shape='single_parent_chain'``.
    Multi-input DAG lineage is a separate effort; when it lands, this
    serializer flips the shape tag and grows edges in ``ancestors``.

    Secret redaction is heuristic (regex on parameter keys). See
    PIPELINE_ERGONOMICS_PLAN.md PE3 §3.2 for the manifest-driven
    follow-up.
    """
    root = db.query(Artifact).filter(Artifact.oid == oid).first()
    if root is None or root.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Walk the parent chain. Bounded depth + cycle guard mirrors the
    # /lineage endpoint's logic (cycles shouldn't happen given
    # immutability + monotonic created_date, but bound is cheap).
    ancestors: List[Artifact] = []
    seen: set = {root.oid}
    cursor = root.source_artifact_id
    truncated = False
    for _ in range(_WORKFLOW_LINEAGE_DEPTH):
        if cursor is None or cursor in seen:
            break
        seen.add(cursor)
        parent = db.query(Artifact).filter(Artifact.oid == cursor).first()
        if parent is None:
            break
        ancestors.append(parent)
        cursor = parent.source_artifact_id
    else:
        # Loop ran to completion — depth cap reached. cursor may still
        # point at an unfollowed ancestor.
        truncated = cursor is not None

    return WorkflowExport(
        exported_at=datetime.utcnow(),
        lineage_shape="single_parent_chain",
        root_artifact=_artifact_to_workflow_node(db, root),
        ancestors=[_artifact_to_workflow_node(db, a) for a in ancestors],
        truncated_at_depth=_WORKFLOW_LINEAGE_DEPTH if truncated else None,
    )

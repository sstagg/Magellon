"""Artifact entity — the typed bridge between jobs in a pipeline.

Phase 4 (2026-05-03). First-class output of any task whose result is
consumed by a downstream task. Today's producers / consumers:

  PARTICLE_EXTRACTION (stack maker)  → emits ``particle_stack``
  TWO_D_CLASSIFICATION (CAN)         → consumes ``particle_stack``
                                     emits ``class_averages``

The DB shape (alembic 0005) is single-table inheritance: one
``artifact`` table, ``kind`` discriminator, queryable hot fields
promoted to columns, long-tail metadata in ``data_json``.

Per ratified rule 1 (project_artifact_bus_invariants.md): the bus
carries refs (``mrcs_path``, ``star_path``) + scalar summaries
(``particle_count``, ``apix``, ``box_size``) only — never the file
content even when small.

Per rule 6: artifacts are immutable once written. A re-run produces a
*new* row pointing at the same source. The SDK model carries no
``update`` semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactKind(str, Enum):
    """Allowed values for ``artifact.kind``.

    String-valued so the wire shape is human-readable. Consumers
    should accept any string and only enforce known kinds at the
    application layer where behavior depends on it (rule 4 — the DB
    column is VARCHAR; this enum is the SDK's app-side validation).
    """

    PARTICLE_STACK = "particle_stack"
    CLASS_AVERAGES = "class_averages"
    STAR_METADATA = "star_metadata"
    VOLUME = "volume"
    MASK = "mask"


class Artifact(BaseModel):
    """Typed bridge between a producing job/task and downstream consumers.

    Mirrors the alembic 0005 ``artifact`` table 1:1 — promoted hot
    fields as real attributes, long-tail metadata in ``data_json``.
    Pydantic validation is the app-side companion to the DB's
    VARCHAR ``kind`` column (rule 4).
    """

    oid: UUID
    kind: str
    """Discriminator. Accept any string for forward-compat; consumers
    that branch on kind should use :class:`ArtifactKind` for the
    known values and treat unknowns as opaque."""

    producing_job_id: Optional[UUID] = None
    producing_task_id: Optional[UUID] = None
    msession_id: Optional[str] = None

    # Promoted hot columns — fields downstream code queries.
    mrcs_path: Optional[str] = None
    star_path: Optional[str] = None
    particle_count: Optional[int] = None
    apix: Optional[float] = None
    box_size: Optional[int] = None

    data_json: Dict[str, Any] = Field(default_factory=dict)

    created_date: datetime = Field(default_factory=_now_utc)
    deleted_at: Optional[datetime] = None
    """Soft-delete timestamp. Per rule 6 the only mutable lifecycle on
    an artifact: bytes-of-record fields never update."""


__all__ = [
    "Artifact",
    "ArtifactKind",
]

"""create artifact table (Phase 4)

Revision ID: 0005_create_artifact
Revises: 0004_add_task_subject_axis
Create Date: 2026-05-03

Phase 4 — Artifact entity. First-class typed output of any task whose
result is consumed by a downstream task. Today's only producer is the
PARTICLE_EXTRACTION plugin (Phase 5) and the only consumer is the
TWO_D_CLASSIFICATION plugin (Phase 7); the table is sized for the
broader pattern (class_averages, volumes, masks, …).

Per ratified rule 2 (project_artifact_bus_invariants.md, 2026-05-03):
single-table inheritance with the queryable hot fields promoted to
real columns. ``data_json`` carries the long tail of per-kind
metadata (CAN hyperparameters, run summaries, etc.).

Per rule 4: ``kind`` is VARCHAR + app validation, not a MySQL ENUM.
Allowed values today: ``'particle_stack' | 'class_averages' |
'star_metadata' | 'volume' | 'mask'``.

Per rule 6: artifacts are immutable. A re-run produces a *new* row
pointing at the same source. ``deleted_at`` is the only mutable field
on a written artifact (soft-delete only).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "0005_create_artifact"
down_revision: Union[str, None] = "0004_add_task_subject_axis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifact",
        # PK + lineage.
        sa.Column("oid", sa.BINARY(length=16), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("producing_job_id", sa.BINARY(length=16), nullable=True),
        sa.Column("producing_task_id", sa.BINARY(length=16), nullable=True),
        sa.Column("msession_id", sa.String(length=100), nullable=True),
        # Promoted hot columns — fields downstream consumers query
        # against. Particle-stack today; volume/mask paths land here
        # too as those kinds appear (kind discriminates).
        sa.Column("mrcs_path", sa.String(length=500), nullable=True),
        sa.Column("star_path", sa.String(length=500), nullable=True),
        sa.Column("particle_count", sa.Integer(), nullable=True),
        sa.Column("apix", sa.Float(), nullable=True),
        sa.Column("box_size", sa.Integer(), nullable=True),
        # Long-tail per-kind metadata (run summaries, hyperparameters).
        sa.Column("data_json", JSON(), nullable=True),
        # Lifecycle.
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # XAF-style optimistic-concurrency field — every other Magellon
        # table carries this; mirror for consistency. Mutating an
        # existing artifact is forbidden (rule 6) but deleted_at +
        # OptimisticLockField may bump if a soft-delete races.
        sa.Column("OptimisticLockField", sa.Integer(), nullable=True),
        sa.Column("GCRecord", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["image_job.oid"],
            name="fk_artifact_producing_job",
        ),
        sa.ForeignKeyConstraint(
            ["producing_task_id"],
            ["image_job_task.oid"],
            name="fk_artifact_producing_task",
        ),
    )

    op.create_index("ix_artifact_kind", "artifact", ["kind"])
    op.create_index(
        "ix_artifact_producing_job_id",
        "artifact",
        ["producing_job_id"],
    )
    op.create_index(
        "ix_artifact_msession_kind",
        "artifact",
        ["msession_id", "kind"],
    )
    op.create_index("ix_artifact_GCRecord", "artifact", ["GCRecord"])


def downgrade() -> None:
    op.drop_index("ix_artifact_GCRecord", table_name="artifact")
    op.drop_index("ix_artifact_msession_kind", table_name="artifact")
    op.drop_index("ix_artifact_producing_job_id", table_name="artifact")
    op.drop_index("ix_artifact_kind", table_name="artifact")
    op.drop_table("artifact")

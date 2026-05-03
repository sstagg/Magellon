"""create pipeline_run + image_job.parent_run_id (Phase 8)

Revision ID: 0006_create_pipeline_run
Revises: 0005_create_artifact
Create Date: 2026-05-03

Phase 8 — PipelineRun rollup. The architectural addition that lets a
user-visible "I ran the picker → extractor → classifier on session
X" map onto the existing image_job rows. Each algorithm step stays
its own ImageJob (per ratified rule from 2026-05-03 architecture
review); ``pipeline_run`` is the parent rollup.

Per ratified rule 4 (project_artifact_bus_invariants.md, 2026-05-03):
``status_id`` is a small smallint (matching image_job's pattern).
``settings`` is JSON for free-form config (cryoSPARC's "Workflow
parameters" surface). Soft-delete via ``deleted_at`` for consistency
with the artifact table (rule 6, immutable spirit).

The ``image_job.parent_run_id`` FK is nullable so existing jobs
created before Phase 8 keep working — they appear as standalone
runs in the UI rollup until the operator (or a backfill) groups
them under a PipelineRun.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "0006_create_pipeline_run"
down_revision: Union[str, None] = "0005_create_artifact"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_run",
        sa.Column("oid", sa.BINARY(length=16), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("msession_id", sa.String(length=100), nullable=True, index=True),
        sa.Column("status_id", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.Column("started_date", sa.DateTime(), nullable=True),
        sa.Column("ended_date", sa.DateTime(), nullable=True),
        # Free-form workflow parameters: pickers, box sizes, classifier
        # hyperparameters, etc. Read by the UI rollup; not authoritative
        # for the per-job runtime (those settings live on image_job).
        sa.Column("settings", JSON(), nullable=True),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        # Lifecycle.
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("OptimisticLockField", sa.Integer(), nullable=True),
        sa.Column("GCRecord", sa.Integer(), nullable=True, index=True),
    )

    op.create_index("ix_pipeline_run_msession_id", "pipeline_run", ["msession_id"])
    op.create_index("ix_pipeline_run_status_id", "pipeline_run", ["status_id"])

    # ImageJob FK to pipeline_run. Nullable so pre-Phase-8 jobs
    # remain valid; new dispatches link explicitly.
    op.add_column(
        "image_job",
        sa.Column("parent_run_id", sa.BINARY(length=16), nullable=True),
    )
    op.create_foreign_key(
        "fk_image_job_parent_run",
        "image_job",
        "pipeline_run",
        ["parent_run_id"],
        ["oid"],
    )
    op.create_index("ix_image_job_parent_run_id", "image_job", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("ix_image_job_parent_run_id", table_name="image_job")
    op.drop_constraint("fk_image_job_parent_run", "image_job", type_="foreignkey")
    op.drop_column("image_job", "parent_run_id")

    op.drop_index("ix_pipeline_run_status_id", table_name="pipeline_run")
    op.drop_index("ix_pipeline_run_msession_id", table_name="pipeline_run")
    op.drop_table("pipeline_run")

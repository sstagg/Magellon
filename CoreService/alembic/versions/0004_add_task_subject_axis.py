"""add subject_kind + subject_id to image_job_task (Phase 3)

Revision ID: 0004_add_task_subject_axis
Revises: 0003_add_task_provenance
Create Date: 2026-05-03

Phase 3 — subject axis. Pre-Phase-3 every task is image-keyed
(``image_id`` FK on ``image_job_task``). The CAN classifier doesn't fit
that mold — its subject is a ``particle_stack``, not an image. Adding
the (kind, id) pair lets the platform talk about non-image-keyed work
without breaking the existing image-keyed flow.

Per ratified rule 4 (project_artifact_bus_invariants.md, 2026-05-03):
``subject_kind`` is VARCHAR(32) + app validation, NOT a MySQL ENUM —
``ALTER TABLE ... MODIFY COLUMN ENUM(...)`` on a tens-of-millions-row
``image_job_task`` is multi-hour downtime; VARCHAR is a code-only
change.

Allowed kinds (validated in the SDK Pydantic model, not the DB):
``'image' | 'particle_stack' | 'session' | 'run' | 'artifact'``.

Backfill keeps existing rows back-compat: every pre-Phase-3 row is
``subject_kind='image', subject_id=image_id``. Image-keyed plugins
keep working unchanged.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_task_subject_axis"
down_revision: Union[str, None] = "0003_add_task_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``subject_kind`` defaulted to 'image' so existing rows + any
    # in-flight inserts during the deploy land with the back-compat
    # value. Drop the default after the backfill in a follow-up
    # migration if we want to force callers to set the field
    # explicitly (probably not — the default is the dominant case).
    op.add_column(
        "image_job_task",
        sa.Column(
            "subject_kind",
            sa.String(length=32),
            nullable=False,
            server_default="image",
        ),
    )
    op.add_column(
        "image_job_task",
        sa.Column("subject_id", sa.BINARY(length=16), nullable=True),
    )

    # Backfill: every existing row is image-keyed.
    op.execute(
        "UPDATE image_job_task SET subject_id = image_id "
        "WHERE image_id IS NOT NULL AND subject_id IS NULL"
    )

    # Common query: "find every task touching this stack". Index on
    # (subject_kind, subject_id) covers it — the kind first because
    # 'image' will dominate; classifier rows are < 1% of total.
    op.create_index(
        "ix_image_job_task_subject",
        "image_job_task",
        ["subject_kind", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_job_task_subject", table_name="image_job_task")
    op.drop_column("image_job_task", "subject_id")
    op.drop_column("image_job_task", "subject_kind")

"""add plugin_id and plugin_version provenance columns to image_job_task

Revision ID: 0003_add_task_provenance
Revises: 0002_create_job_event
Create Date: 2026-04-15

Per-task provenance (P4). The image_job table already carries a
``plugin_id`` for the *job* (which plugin owns the workflow); this
adds the same pair to ``image_job_task`` so each individual result
records which plugin + version produced it.

Both columns are nullable: existing rows pre-date the field, and
plugins that haven't been migrated to populate them yet still need
their results accepted.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_task_provenance"
down_revision: Union[str, None] = "0002_create_job_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "image_job_task",
        sa.Column("plugin_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "image_job_task",
        sa.Column("plugin_version", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_image_job_task_plugin_id",
        "image_job_task",
        ["plugin_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_job_task_plugin_id", table_name="image_job_task")
    op.drop_column("image_job_task", "plugin_version")
    op.drop_column("image_job_task", "plugin_id")

"""create job_event table

Revision ID: 0002_create_job_event
Revises: 0001_add_plugin_columns
Create Date: 2026-04-15

Append-only log of plugin lifecycle events. ``event_id`` has a UNIQUE
index so the same CloudEvents id arriving on both RMQ and NATS dedupes
to a single row (INSERT … ON DUPLICATE KEY no-ops the second insert).

Named ``job_event`` (not ``image_job_event``) so future non-image jobs
can share the log without a rename.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_create_job_event"
down_revision: Union[str, None] = "0001_add_plugin_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_event",
        sa.Column("oid", sa.BINARY(16), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.BINARY(16), sa.ForeignKey("image_job.oid"), nullable=False),
        sa.Column("task_id", sa.BINARY(16), sa.ForeignKey("image_job_task.oid"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=False),
    )
    op.create_index("ux_job_event_event_id", "job_event", ["event_id"], unique=True)
    op.create_index("ix_job_event_job_id", "job_event", ["job_id"])
    op.create_index("ix_job_event_task_id", "job_event", ["task_id"])
    op.create_index("ix_job_event_event_type", "job_event", ["event_type"])
    op.create_index("ix_job_event_step", "job_event", ["step"])


def downgrade() -> None:
    op.drop_index("ix_job_event_step", table_name="job_event")
    op.drop_index("ix_job_event_event_type", table_name="job_event")
    op.drop_index("ix_job_event_task_id", table_name="job_event")
    op.drop_index("ix_job_event_job_id", table_name="job_event")
    op.drop_index("ux_job_event_event_id", table_name="job_event")
    op.drop_table("job_event")

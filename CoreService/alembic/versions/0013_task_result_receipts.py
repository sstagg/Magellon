"""Processed-result receipts and the result dead-letter table

Revision ID: 0013_task_result_receipts
Revises: 0012_import_queue_microseconds
Create Date: 2026-10-30

task_result_receipt: one row per (task, step) whose plugin result has been
applied. Result processing inserts it in the same transaction as the result,
so a result redelivered after a crash or restart is recognised and skipped.

task_result_dead_letter: results that still failed after their retries are
kept here (with the error and the payload) instead of being dropped.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME


revision: str = "0013_task_result_receipts"
down_revision: Union[str, None] = "0012_import_queue_microseconds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_result_receipt",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("step", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(36), index=True),
        sa.Column("processed_at", DATETIME(fsp=6), nullable=False),
    )
    op.create_table(
        "task_result_dead_letter",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("queue", sa.String(128)),
        sa.Column("task_id", sa.String(36), index=True),
        sa.Column("job_id", sa.String(36), index=True),
        sa.Column("step", sa.String(32)),
        sa.Column("error", sa.Text),
        sa.Column("payload", sa.JSON),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False),
        sa.Column("replayed_at", DATETIME(fsp=6)),
    )


def downgrade() -> None:
    op.drop_table("task_result_dead_letter")
    op.drop_table("task_result_receipt")

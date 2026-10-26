"""import_job_queue timestamps with microseconds

Revision ID: 0012_import_queue_microseconds
Revises: 0011_import_job_queue
Create Date: 2026-10-23

0011 created the timestamps as MySQL DATETIME, which stores whole seconds.
Imports submitted within the same second then tied on ``created_at`` and
ran in arbitrary order. DATETIME(6) keeps microseconds, so each user's
imports run in the order they were submitted.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects.mysql import DATETIME


revision: str = "0012_import_queue_microseconds"
down_revision: Union[str, None] = "0011_import_job_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (("created_at", False), ("started_at", True), ("finished_at", True), ("heartbeat_at", True))


def upgrade() -> None:
    for name, nullable in _COLUMNS:
        op.alter_column("import_job_queue", name, type_=DATETIME(fsp=6), existing_nullable=nullable)


def downgrade() -> None:
    for name, nullable in _COLUMNS:
        op.alter_column("import_job_queue", name, type_=DATETIME(), existing_nullable=nullable)

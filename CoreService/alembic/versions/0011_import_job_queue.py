"""Durable import queue (import_job_queue)

Revision ID: 0011_import_job_queue
Revises: 0010_artifact_dispatch_cache
Create Date: 2026-10-23

Imports used to run as in-process background threads of the web backend,
all at once and lost on any restart. Each submitted import is now a row
here; separate import-worker processes claim rows (fairly across users),
run them, heartbeat while running, and record the outcome. Waiting imports
survive backend and worker restarts, and the API can report each one's
place in line.

One row per import job; ``id`` is the job id handed to the browser and
later used for the ``image_job`` row the importer creates when it runs.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "0011_import_job_queue"
down_revision: Union[str, None] = "0010_artifact_dispatch_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_job_queue",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),          # leginon, epu, epu_job, magellon, serialem
        sa.Column("label", sa.String(length=255), nullable=True),         # what the user is importing (session name)
        sa.Column("owner_id", sa.String(length=36), nullable=True),       # sys_sec_user.oid as text
        sa.Column("payload", JSON, nullable=False),                       # importer parameters, JSON-serialised
        sa.Column("status", sa.String(length=16), nullable=False),        # queued | running | done | failed | cancelled
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("worker", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    # Claiming and position queries filter by status and walk by age.
    op.create_index("ix_import_job_queue_status_created", "import_job_queue", ["status", "created_at"])
    op.create_index("ix_import_job_queue_owner_status", "import_job_queue", ["owner_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_import_job_queue_owner_status", table_name="import_job_queue")
    op.drop_index("ix_import_job_queue_status_created", table_name="import_job_queue")
    op.drop_table("import_job_queue")

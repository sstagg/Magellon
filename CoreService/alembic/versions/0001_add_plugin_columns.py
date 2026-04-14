"""add plugin_id and settings columns to image_job

Revision ID: 0001_add_plugin_columns
Revises:
Create Date: 2026-04-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_add_plugin_columns"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "image_job",
        sa.Column("plugin_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_image_job_plugin_id",
        "image_job",
        ["plugin_id"],
    )
    op.add_column(
        "image_job",
        sa.Column("settings", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_job", "settings")
    op.drop_index("ix_image_job_plugin_id", table_name="image_job")
    op.drop_column("image_job", "plugin_id")

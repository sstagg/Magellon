"""add artifact.source_artifact_id FK for class-average lineage (High #5)

Revision ID: 0007_add_artifact_source_fk
Revises: 0006_create_pipeline_run
Create Date: 2026-05-04

Reviewer-flagged High #5 fix. Pre-fix lineage between
``class_averages`` artifacts (TWO_D_CLASSIFICATION output) and the
``particle_stack`` they were classified from lived only in
``artifact.data_json['source_particle_stack_id']``. That meant
"every classification of stack X" was a JSON-contains scan with no
FK integrity, and a deleted source stack left dangling lineage.

This migration promotes the link to a real FK column. Per ratified
rule 6 (artifact immutability) the column is set at write time and
never updated; soft-delete on the source still works because the FK
is nullable + ON DELETE SET NULL.

Lineage stays in ``data_json`` as a back-compat copy for one release
(downstream code that already reads it keeps working). The writer
populates BOTH; the cutover to drop the JSON key is a follow-up.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_artifact_source_fk"
down_revision: Union[str, None] = "0006_create_pipeline_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "artifact",
        sa.Column("source_artifact_id", sa.BINARY(length=16), nullable=True),
    )
    op.create_foreign_key(
        "fk_artifact_source",
        "artifact",
        "artifact",
        ["source_artifact_id"],
        ["oid"],
        ondelete="SET NULL",
    )
    # Hot query: "all classifications of this particle_stack". Index
    # on the FK keeps it cheap.
    op.create_index(
        "ix_artifact_source_artifact_id",
        "artifact",
        ["source_artifact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_source_artifact_id", table_name="artifact")
    op.drop_constraint("fk_artifact_source", "artifact", type_="foreignkey")
    op.drop_column("artifact", "source_artifact_id")

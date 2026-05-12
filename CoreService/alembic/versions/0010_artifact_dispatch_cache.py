"""Add dispatch-cache columns + covering index to artifact (PE2)

Revision ID: 0010_artifact_dispatch_cache
Revises: 0009_plugin_endpoint
Create Date: 2026-05-12

PE2 (PIPELINE_ERGONOMICS_PLAN.md §PE2) wants to deduplicate dispatch
when the same plugin at the same version is asked to run with the
same input artifact set and the same parameters. The cache key:

    SHA-256 of (plugin_id, plugin_version, sorted(input_oids),
                canonicalized_params_json, category)

Four columns hold the per-Artifact piece of that key so the cache
lookup is one indexed point query:

  - ``producer_plugin_id``      — slug from PluginManifest.plugin_id
  - ``producer_plugin_version`` — value from PluginManifest.version
  - ``params_hash``             — SHA-256 of canonical JSON of params
  - ``input_set_hash``          — SHA-256 of sorted input artifact OIDs

All four nullable so pre-PE2 artifact rows survive untouched. The
cache lookup filters on ``deleted_at IS NULL`` so superseded rows
fall through to a real dispatch (per the plan's invalidation rule
#2 — "input artifact superseded").

The composite index covers the lookup predicate exactly. Without it,
the cache hit path would be a full table scan on every dispatch and
PE2 would *slow down* the system instead of speeding it up.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_artifact_dispatch_cache"
down_revision: Union[str, None] = "0009_plugin_endpoint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Index name kept short — InnoDB caps identifier length and the
# default ix_artifact_<col1>_<col2>_<col3>_<col4> would be cramped.
_CACHE_INDEX_NAME = "ix_artifact_dispatch_cache"


def upgrade() -> None:
    op.add_column(
        "artifact",
        sa.Column("producer_plugin_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "artifact",
        sa.Column("producer_plugin_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "artifact",
        sa.Column("params_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "artifact",
        sa.Column("input_set_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        _CACHE_INDEX_NAME,
        "artifact",
        [
            "producer_plugin_id",
            "producer_plugin_version",
            "params_hash",
            "input_set_hash",
        ],
    )


def downgrade() -> None:
    op.drop_index(_CACHE_INDEX_NAME, table_name="artifact")
    op.drop_column("artifact", "input_set_hash")
    op.drop_column("artifact", "params_hash")
    op.drop_column("artifact", "producer_plugin_version")
    op.drop_column("artifact", "producer_plugin_id")

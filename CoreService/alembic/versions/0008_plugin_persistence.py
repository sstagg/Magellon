"""PM1: extend plugin table; add plugin_state + plugin_category_default

Revision ID: 0008_plugin_persistence
Revises: 0007_add_artifact_source_fk
Create Date: 2026-05-04

PM1 of PLUGIN_MANAGER_PLAN.md (revised 2026-05-04). Adds the
persistence layer the in-memory PluginStateStore +
InstalledPluginsRegistry pretended to have. Closes G1/G2/G8 from the
plan: silent state loss on restart and the unused legacy ``plugin``
table.

Identity layers (per PLUGIN_MANAGER_PLAN §0):

  plugin.oid              — DB row identity / FK target (existing)
  manifest_plugin_id      — install package identity (NEW)
  (category, backend_id)  — dispatch identity (NEW columns)
  instance_id             — live replica identity (lives in liveness registry)
  plugin_category_default — default routing policy (NEW table)

Schema additions:

  * Widen plugin.version VARCHAR(10) → VARCHAR(64) (SemVer with
    prerelease tags).
  * Promote catalog hot fields onto plugin: ``manifest_plugin_id``,
    ``backend_id``, ``category``, ``schema_version``,
    ``install_method``, ``install_dir``, ``image_ref``,
    ``container_ref``, ``archive_id``, ``manifest_json``,
    ``installed_date``.
  * NEW ``plugin_state``: per-plugin operator-mutable runtime state
    (``enabled`` flag + heartbeat mirror). FK plugin_oid → plugin.oid.
    PM1 ships ONLY the enabled flag — reviewer-flagged Medium #6
    splits paused* into PM4's alembic 0009.
  * NEW ``plugin_category_default``: per-category default routing
    policy. PK=category. Multi-category plugins have multiple rows
    per category they're default for (reviewer-flagged High #1: topaz
    serves TOPAZ_PARTICLE_PICKING + MICROGRAPH_DENOISING, can be
    default for one but not the other).

Per ratified rule 4: VARCHAR for the kind/method discriminators
(``install_method``, ``manifest_plugin_id`` slug), not MySQL ENUM —
plugin set evolves.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


revision: str = "0008_plugin_persistence"
down_revision: Union[str, None] = "0007_add_artifact_source_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen version field. Pre-existing column has at most one
    # populated row in production (the pp/template_picker sentinel
    # with version=NULL); the widening is safe and one-shot.
    op.alter_column(
        "plugin",
        "version",
        existing_type=sa.String(length=10),
        type_=sa.String(length=64),
    )

    # Promoted catalog hot fields. NOTE: ``manifest_plugin_id``
    # (NOT ``plugin_id``). The latter would collide with the
    # existing ``image_meta_data.plugin_id`` FK to plugin.oid —
    # reviewer-flagged High #2 from the first revision of the plan.
    op.add_column(
        "plugin",
        sa.Column("manifest_plugin_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("backend_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("category", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("schema_version", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("install_method", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("install_dir", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("image_ref", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("container_ref", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("archive_id", sa.String(length=64), nullable=True),
    )
    op.add_column("plugin", sa.Column("manifest_json", JSON(), nullable=True))
    op.add_column(
        "plugin",
        sa.Column("installed_date", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "ix_plugin_manifest_plugin_id", "plugin", ["manifest_plugin_id"]
    )
    op.create_index(
        "ix_plugin_category_backend",
        "plugin",
        ["category", "backend_id"],
    )

    # plugin_state — mutable operator state. FK to plugin.oid.
    op.create_table(
        "plugin_state",
        sa.Column("plugin_oid", sa.BINARY(length=16), primary_key=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("OptimisticLockField", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_oid"],
            ["plugin.oid"],
            name="fk_plugin_state_plugin",
            ondelete="CASCADE",
        ),
    )

    # plugin_category_default — default routing policy.
    # PK=category (one default per category at most). Multi-category
    # plugins get multiple rows pointing at them, one per category.
    op.create_table(
        "plugin_category_default",
        sa.Column("category", sa.String(length=64), primary_key=True),
        sa.Column("plugin_oid", sa.BINARY(length=16), nullable=False),
        sa.Column("set_at", sa.DateTime(), nullable=False),
        sa.Column("set_by_user_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_oid"],
            ["plugin.oid"],
            name="fk_pcd_plugin",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pcd_plugin_oid", "plugin_category_default", ["plugin_oid"]
    )


def downgrade() -> None:
    op.drop_index("ix_pcd_plugin_oid", table_name="plugin_category_default")
    op.drop_table("plugin_category_default")
    op.drop_table("plugin_state")

    op.drop_index("ix_plugin_category_backend", table_name="plugin")
    op.drop_index("ix_plugin_manifest_plugin_id", table_name="plugin")

    for col in (
        "installed_date",
        "manifest_json",
        "archive_id",
        "container_ref",
        "image_ref",
        "install_dir",
        "install_method",
        "schema_version",
        "category",
        "backend_id",
        "manifest_plugin_id",
    ):
        op.drop_column("plugin", col)

    op.alter_column(
        "plugin",
        "version",
        existing_type=sa.String(length=64),
        type_=sa.String(length=10),
    )

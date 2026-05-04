"""Add http_endpoint + port to plugin catalog

Revision ID: 0009_plugin_endpoint
Revises: 0008_plugin_persistence
Create Date: 2026-05-04

The install pipeline already allocates a port for the plugin's
FastAPI host (PluginPortAllocator, persisted in
``<plugins_dir>/.port_assignments.json``) and writes it into the
plugin's ``runtime.env`` along with a derived ``MAGELLON_PLUGIN_HTTP_ENDPOINT``.
The runtime values also flow into the announce envelope so
sync_dispatcher can route SYNC/PREVIEW calls.

Pre-0009 the catalog row didn't carry either. Operators / the React
plugin manager UI couldn't tell from a single SELECT where an
installed plugin was reachable — they had to either look at
the .port_assignments JSON sidecar or query the live registry.

0009 promotes both as catalog hot fields. Liveness registry stays
the source of truth for *current* reachability (heartbeat-fresh);
the catalog row is the install-time fact (operator-pinned).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_plugin_endpoint"
down_revision: Union[str, None] = "0008_plugin_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plugin",
        sa.Column("http_endpoint", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "plugin",
        sa.Column("port", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plugin", "port")
    op.drop_column("plugin", "http_endpoint")

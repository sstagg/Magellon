"""Baseline: create the full pre-alembic base schema.

Root of the migration chain. Before this existed, migration 0001
assumed a dump-restored database, so ``alembic upgrade head`` could
never build a working schema from an empty MySQL — new environments
depended on hand-loading ``database/magellon01db.sql``.

Executes ``alembic/baseline_schema.sql`` (the dump's DDL with data,
LOCK, and DROP statements stripped). Safety: refuses to run against a
database that already has the base schema — an existing environment
must be adopted with ``alembic stamp`` instead (see
Documentation/PRODUCTION_READINESS.md), never rebuilt.

Revision ID: 0000_baseline_schema
Revises:
Create Date: 2026-07-06
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0000_baseline_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASELINE_SQL = Path(__file__).resolve().parents[1] / "baseline_schema.sql"

# Table whose presence marks an already-provisioned database.
_SENTINEL_TABLE = "image"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_SENTINEL_TABLE):
        raise RuntimeError(
            "Refusing to apply the baseline: this database already has the "
            f"base schema (found table {_SENTINEL_TABLE!r}). Adopt it with "
            "'alembic stamp <revision>' matching its actual state instead."
        )

    raw = _BASELINE_SQL.read_text(encoding="utf-8")
    bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
    try:
        for statement in _split_statements(raw):
            bind.exec_driver_sql(statement)
    finally:
        bind.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


def _split_statements(raw: str) -> list:
    """Split dump SQL into executable statements.

    DELIMITER-aware so stored-routine bodies (e.g. ``update_levels``,
    dumped inside a ``DELIMITER $$ ... $$ DELIMITER ;`` block) stay a
    single statement instead of being broken at every inner ``;``.
    """
    statements = []
    delimiter = ";"
    buffer: list = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1].strip()
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).strip()
            statement = statement[: -len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer = []
    leftover = "\n".join(buffer).strip()
    if leftover:
        statements.append(leftover)
    return statements


def downgrade() -> None:
    raise NotImplementedError(
        "The baseline is not reversible; drop the database instead."
    )

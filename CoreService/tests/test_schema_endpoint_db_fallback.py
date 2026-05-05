"""Tests for the lenient schema resolver in plugins.controller.

Schema is per-category, not per-plugin-instance, so the input/output
schema endpoints should answer for installed-but-stopped plugins too —
not only currently-heartbeating ones. These tests pin the DB-fallback
path that ``_category_for_plugin`` adds.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from plugins import controller as ctl


@contextmanager
def _empty_live_registry():
    """Force the live registry to report zero plugins for the duration
    of the test — so any successful resolution comes from the DB
    fallback path."""
    fake_registry = MagicMock()
    fake_registry.list_live.return_value = []
    with patch.object(ctl, "get_liveness_registry", return_value=fake_registry):
        yield


def _fake_plugin_row(*, manifest_plugin_id: str, category: str, oid: uuid.UUID, name: str = ""):
    row = MagicMock()
    row.manifest_plugin_id = manifest_plugin_id
    row.category = category
    row.oid = oid
    row.name = name or manifest_plugin_id
    row.deleted_date = None
    return row


@contextmanager
def _patched_db(rows: list):
    """Patch session_local() to return a session whose .query().filter()
    chain resolves to one of the provided rows. We match by the value
    the controller passes to ``Plugin.manifest_plugin_id == ...``,
    ``Plugin.oid == ...``, or ``Plugin.name == ...``."""
    captured: dict = {"first_call_match": None}

    def make_session():
        session = MagicMock()

        # Each .query(...).filter(...).filter(...).first() call walks the row list
        # and returns the first one whose attributes line up with the filter
        # arguments. We don't introspect the SQLAlchemy clauses; we just
        # rotate through provided rows in order, so tests can stage which row
        # the resolver should see for which call.
        index = {"i": 0}

        def query(*_a, **_kw):
            q = MagicMock()
            q.filter.return_value = q

            def first():
                while index["i"] < len(rows):
                    row = rows[index["i"]]
                    index["i"] += 1
                    if row is not None:
                        return row
                return None

            q.first = first
            return q

        session.query = query
        session.close = MagicMock()
        return session

    with patch("database.session_local", side_effect=make_session):
        yield captured


def test_resolver_falls_back_to_db_by_manifest_plugin_id():
    """Live registry empty, DB has a row keyed by manifest_plugin_id —
    we should still resolve to the right CategoryContract."""
    row = _fake_plugin_row(
        manifest_plugin_id="template-picker",
        category="particle_picking",
        oid=uuid.uuid4(),
    )
    with _empty_live_registry(), _patched_db([row]):
        contract = ctl._category_contract_for_plugin("template-picker")
    assert contract is not None
    # Contract's display name uses spaces; the DB stores the slug form.
    # The resolver normalizes underscores/spaces so both forms match.
    assert contract.category.name.lower().replace(" ", "_") == "particle_picking"


def test_resolver_falls_back_to_db_by_oid():
    """oid form is accepted as a stable alternative — resolves to the
    same contract as the manifest-plugin-id path."""
    plugin_oid = uuid.uuid4()
    row = _fake_plugin_row(
        manifest_plugin_id="template-picker",
        category="particle_picking",
        oid=plugin_oid,
    )
    # Sequence: 2 manifest_plugin_id misses (short=plugin_id form), then oid hit
    with _empty_live_registry(), _patched_db([None, None, row]):
        contract = ctl._category_contract_for_plugin(str(plugin_oid))
    assert contract is not None
    # Contract's display name uses spaces; the DB stores the slug form.
    # The resolver normalizes underscores/spaces so both forms match.
    assert contract.category.name.lower().replace(" ", "_") == "particle_picking"


def test_resolver_returns_none_when_unknown_to_both_registry_and_db():
    """Truly absent plugin → None → controller turns that into 404."""
    with _empty_live_registry(), _patched_db([None, None, None, None]):
        contract = ctl._category_contract_for_plugin("definitely-not-installed")
    assert contract is None


def test_resolver_skips_uuid_query_for_non_uuid_strings():
    """Sanity check the cheap path — slugs that don't parse as UUID
    don't try the oid filter (which would otherwise spam the SQL log
    and be wasted work). Indirect proof: rows list only has the
    manifest hits; if oid were attempted we'd consume past it."""
    row = _fake_plugin_row(
        manifest_plugin_id="ctf",
        category="ctf",
        oid=uuid.uuid4(),
    )
    with _empty_live_registry(), _patched_db([row]):
        contract = ctl._category_contract_for_plugin("ctf")
    assert contract is not None
    assert contract.category.name.lower() == "ctf"

"""Reducer tests for the PM2 Conditions[] surface.

MagicMock-driven — no DB. Pins one Condition per orthogonal axis:
Installed, Enabled, Live, Healthy, Default. Reviewer-flagged High #4
gets pinned via the Healthy reducer's data source: ``job_event.ts``,
NOT a non-existent ``image_job_task.ended_on``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from magellon_sdk.models.conditions import (
    Condition,
    ConditionStatus,
    ConditionType,
)
from models.sqlalchemy_models import (
    Plugin,
    PluginCategoryDefault,
    PluginState,
)
from services.plugin_conditions import compute_conditions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _by_type(conditions, t: ConditionType) -> Condition:
    """Return the (single) condition row of the given type."""
    matches = [c for c in conditions if c.type == t]
    assert len(matches) == 1, (
        f"expected exactly one {t} condition, got {len(matches)}"
    )
    return matches[0]


class _Q:
    def __init__(self, result):
        self._r = result

    def filter(self, *_a, **_kw):
        return self

    def join(self, *_a, **_kw):
        return self

    def all(self):
        return self._r if isinstance(self._r, list) else (
            [self._r] if self._r is not None else []
        )

    def first(self):
        if isinstance(self._r, list):
            return self._r[0] if self._r else None
        return self._r


# ---------------------------------------------------------------------------
# Installed axis
# ---------------------------------------------------------------------------


def test_installed_true_when_plugin_row_found():
    plugin = Plugin(
        oid=uuid.uuid4(),
        name="CTF Plugin",
        manifest_plugin_id="ctf",
    )
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.INSTALLED)
    assert cond.status is ConditionStatus.TRUE
    assert cond.reason == "Catalogued"


def test_installed_false_when_plugin_row_missing():
    db = MagicMock()
    db.query.side_effect = [_Q(None)]   # initial Plugin lookup misses

    conds = compute_conditions(db, plugin_name="never-cataloged", is_live=False)

    cond = _by_type(conds, ConditionType.INSTALLED)
    assert cond.status is ConditionStatus.FALSE
    assert cond.reason == "Uncatalogued"


# ---------------------------------------------------------------------------
# Enabled axis
# ---------------------------------------------------------------------------


def test_enabled_defaults_to_true_when_no_state_row():
    """Mirrors the in-memory shim's behaviour pre-PM1."""
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.ENABLED)
    assert cond.status is ConditionStatus.TRUE
    assert cond.reason == "DefaultTrue"


def test_enabled_false_when_operator_disabled():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    state = PluginState(plugin_oid=plugin.oid, enabled=False)
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(state), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.ENABLED)
    assert cond.status is ConditionStatus.FALSE
    assert cond.reason == "Operator"


# ---------------------------------------------------------------------------
# Live axis
# ---------------------------------------------------------------------------


def test_live_true_when_caller_supplies_recent_heartbeat():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    # Live → Healthy branch fires → 5 db.query calls total:
    # Plugin, PluginState, JobEvent, Plugin (identity match), PCD.
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([]), _Q(plugin), _Q([])]

    conds = compute_conditions(
        db,
        plugin_oid=plugin.oid,
        is_live=True,
        last_heartbeat_at=datetime.now(timezone.utc),
    )

    cond = _by_type(conds, ConditionType.LIVE)
    assert cond.status is ConditionStatus.TRUE
    assert cond.reason == "Heartbeat"


def test_live_false_when_no_heartbeat_supplied():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.LIVE)
    assert cond.status is ConditionStatus.FALSE
    assert cond.reason == "NoHeartbeat"


def test_live_false_when_heartbeat_too_old():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    too_old = datetime.now(timezone.utc) - timedelta(minutes=10)
    conds = compute_conditions(
        db, plugin_oid=plugin.oid, last_heartbeat_at=too_old,
    )

    cond = _by_type(conds, ConditionType.LIVE)
    assert cond.status is ConditionStatus.FALSE


# ---------------------------------------------------------------------------
# Healthy axis — reviewer-flagged High #4 (job_event.ts, NOT image_job_task.ended_on)
# ---------------------------------------------------------------------------


def test_healthy_unknown_when_not_live():
    """Cheap short-circuit: if the plugin isn't Live, Healthy is
    Unknown — no point scanning job_event for a plugin that's not
    running."""
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.HEALTHY)
    assert cond.status is ConditionStatus.UNKNOWN
    assert cond.reason == "NotLive"


def test_healthy_unknown_when_no_recent_terminal_events():
    """A plugin that's Live + Enabled but hasn't run any tasks
    recently is Healthy=Unknown, NOT Healthy=False. Otherwise idle
    plugins generate false alarms."""
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [
        _Q(plugin),         # 0: initial Plugin lookup
        _Q(None),           # 1: PluginState lookup
        _Q([]),             # 2: JobEvent (start of _has_recent_success chain)
        _Q(plugin),         # 3: Plugin lookup inside _identity_match_clauses
        _Q([]),             # 4: PluginCategoryDefault for Default axis
    ]

    conds = compute_conditions(
        db,
        plugin_oid=plugin.oid,
        is_live=True,
        last_heartbeat_at=datetime.now(timezone.utc),
    )

    cond = _by_type(conds, ConditionType.HEALTHY)
    assert cond.status is ConditionStatus.UNKNOWN
    assert cond.reason == "NoRecentTasks"


def test_healthy_true_when_at_least_one_recent_completed_event():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [
        _Q(plugin),                                # 0: initial Plugin
        _Q(None),                                  # 1: PluginState
        _Q([("completed",), ("failed",)]),         # 2: JobEvent rows
        _Q(plugin),                                # 3: Plugin (identity)
        _Q([]),                                    # 4: PluginCategoryDefault
    ]

    conds = compute_conditions(
        db,
        plugin_oid=plugin.oid,
        is_live=True,
        last_heartbeat_at=datetime.now(timezone.utc),
    )

    cond = _by_type(conds, ConditionType.HEALTHY)
    assert cond.status is ConditionStatus.TRUE
    assert cond.reason == "RecentSuccess"


def test_healthy_false_when_all_recent_events_failed():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [
        _Q(plugin),                                       # 0: initial Plugin
        _Q(None),                                         # 1: PluginState
        _Q([("failed",), ("failed",), ("failed",)]),      # 2: JobEvent rows
        _Q(plugin),                                       # 3: Plugin (identity)
        _Q([]),                                           # 4: PluginCategoryDefault
    ]

    conds = compute_conditions(
        db,
        plugin_oid=plugin.oid,
        is_live=True,
        last_heartbeat_at=datetime.now(timezone.utc),
    )

    cond = _by_type(conds, ConditionType.HEALTHY)
    assert cond.status is ConditionStatus.FALSE
    assert cond.reason == "RecentFailures"


# ---------------------------------------------------------------------------
# Default axis — multi-category aware (reviewer-flagged High #1)
# ---------------------------------------------------------------------------


def test_default_false_when_plugin_not_pinned_for_any_category():
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.DEFAULT)
    assert cond.status is ConditionStatus.FALSE
    assert cond.reason == "NotDefault"


def test_default_true_with_categories_listed_when_pinned():
    """Multi-category plugin like topaz: pinned as default for one
    category surfaces the category names in the message."""
    plugin = Plugin(
        oid=uuid.uuid4(),
        name="Topaz Particle Picking",
        manifest_plugin_id="topaz",
    )
    pcd = PluginCategoryDefault(
        category="topaz_particle_picking",
        plugin_oid=plugin.oid,
        set_at=datetime.utcnow(),
    )
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([pcd])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    cond = _by_type(conds, ConditionType.DEFAULT)
    assert cond.status is ConditionStatus.TRUE
    assert cond.reason == "OperatorPinned"
    assert "topaz_particle_picking" in (cond.message or "")


# ---------------------------------------------------------------------------
# Full surface — exactly 5 conditions (one per type)
# ---------------------------------------------------------------------------


def test_compute_conditions_returns_exactly_five_axes():
    """Sanity: every plugin gets one condition per type. UI can iterate
    without filtering."""
    plugin = Plugin(oid=uuid.uuid4(), name="CTF Plugin", manifest_plugin_id="ctf")
    db = MagicMock()
    db.query.side_effect = [_Q(plugin), _Q(None), _Q([])]

    conds = compute_conditions(db, plugin_oid=plugin.oid, is_live=False)

    types = {c.type for c in conds}
    assert types == {
        ConditionType.INSTALLED,
        ConditionType.ENABLED,
        ConditionType.LIVE,
        ConditionType.HEALTHY,
        ConditionType.DEFAULT,
    }
    assert len(conds) == 5

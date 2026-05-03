"""Unit tests for the PM3 PluginManagerService facade.

Constructor-injected per the plan's PM3 acceptance: every collaborator
is faked, so no DB and no monkey-patching. One test per public read
method (the plan requires 6) plus mutation pass-through tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from magellon_sdk.models import (
    Capability,
    ConditionStatus,
    ConditionType,
    IsolationLevel,
    Transport,
)
from services.plugin_manager import (
    CatalogVersionInfo,
    PluginManagerService,
    PluginView,
    _semver_severity,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeStateStore:
    """Stand-in for PluginStateStore. Records writes; reads return
    whatever's in ``enabled`` / ``defaults`` (both default-True for
    enabled, None-by-default for defaults — matches PluginStateStore)."""

    def __init__(self):
        self.enabled = {}
        self.defaults = {}
        self.set_enabled_calls = []
        self.set_default_calls = []

    def is_enabled(self, plugin_id):
        return self.enabled.get(plugin_id, True)

    def get_default(self, category):
        return self.defaults.get((category or "").lower())

    def set_enabled(self, plugin_id, enabled):
        self.enabled[plugin_id] = enabled
        self.set_enabled_calls.append((plugin_id, enabled))

    def set_default(self, category, plugin_id):
        self.defaults[(category or "").lower()] = plugin_id
        self.set_default_calls.append((category, plugin_id))


def _make_liveness_entry(
    plugin_id,
    category="ctf",
    *,
    instance_id=None,
    manifest=None,
    last_heartbeat=None,
    task_queue=None,
):
    """Cheap PluginLivenessEntry stand-in. Real class refuses kwargs the
    SDK doesn't expose, so SimpleNamespace keeps tests independent."""
    return SimpleNamespace(
        plugin_id=plugin_id,
        plugin_version="1.0.0",
        category=category,
        instance_id=instance_id or "i-1",
        manifest=manifest,
        last_heartbeat=last_heartbeat or datetime.now(timezone.utc),
        status=None,
        task_queue=task_queue,
        backend_id=plugin_id,
    )


def _make_manifest(name="ctffind4", version="1.0.0", category="ctf"):
    """Minimal PluginManifest with the fields the view-builder reads."""
    return SimpleNamespace(
        info=SimpleNamespace(
            name=name,
            version=version,
            schema_version="1",
            description=f"{name} runner",
            developer="Magellon Team",
        ),
        capabilities=[Capability.IDEMPOTENT],
        supported_transports=[Transport.RMQ],
        default_transport=Transport.RMQ,
        isolation=IsolationLevel.CONTAINER,
    )


def _make_in_process_registry(plugin_ids=()):
    reg = MagicMock()
    reg.list.return_value = [
        SimpleNamespace(plugin_id=pid) for pid in plugin_ids
    ]
    return reg


def _make_liveness_registry(entries=()):
    reg = MagicMock()
    reg.list_live.return_value = list(entries)
    return reg


def _make_plugin_repo(rows=()):
    repo = MagicMock()
    repo.list_installed.return_value = list(rows)
    return repo


def _build_manager(*, in_proc=(), live=(), catalog=(), state=None):
    return PluginManagerService(
        in_process=_make_in_process_registry(in_proc),
        liveness=_make_liveness_registry(live),
        state_store=state or _FakeStateStore(),
        plugin_repo=_make_plugin_repo(catalog),
    )


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


def test_list_all_joins_in_process_and_broker_kinds():
    """``kind`` is derived from cross-referencing the in-process
    registry — a plugin in both shows up as in-process; otherwise
    broker. Pinned because the controller's UI relies on this label
    to decide whether the /jobs path or the bus path applies."""
    in_proc = _make_liveness_entry("template-picker", category="pp",
                                   manifest=_make_manifest(name="template-picker"))
    broker = _make_liveness_entry("ctffind4", category="ctf",
                                  manifest=_make_manifest(name="ctffind4"))

    manager = _build_manager(
        in_proc=["pp/template-picker"],
        live=[in_proc, broker],
    )

    views = manager.list_all()
    by_id = {v.plugin_id: v for v in views}
    assert by_id["pp/template-picker"].kind == "in-process"
    assert by_id["ctf/ctffind4"].kind == "broker"


def test_list_all_auto_seeds_default_impl_for_first_live_per_category():
    """First live plugin per category → operator default. Preserves
    legacy ``GET /plugins/`` side-effect so byte-shape is identical."""
    state = _FakeStateStore()
    manager = _build_manager(
        live=[_make_liveness_entry("ctffind4", category="ctf",
                                   manifest=_make_manifest())],
        state=state,
    )
    manager.list_all()
    assert state.set_default_calls == [("ctf", "ctffind4")]


def test_list_all_dedupes_by_composed_plugin_id():
    """Two heartbeats with the same plugin_id (e.g. replicas) collapse
    to one row in the discovery list — replica fan-out is PM5's job."""
    a = _make_liveness_entry("ctffind4", manifest=_make_manifest(),
                             instance_id="i-1")
    b = _make_liveness_entry("ctffind4", manifest=_make_manifest(),
                             instance_id="i-2")
    manager = _build_manager(live=[a, b])
    views = manager.list_all()
    assert len([v for v in views if v.plugin_id == "ctf/ctffind4"]) == 1


def test_list_all_falls_back_for_announceless_heartbeat():
    """Heartbeat-only entry (Announce missed) still surfaces with a
    placeholder description — the operator at least sees the plugin."""
    no_manifest = _make_liveness_entry("ctffind4", manifest=None)
    manager = _build_manager(live=[no_manifest])
    [view] = manager.list_all()
    assert "manifest pending" in view.description
    assert view.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# list_installed
# ---------------------------------------------------------------------------


def test_list_installed_returns_catalog_rows_even_when_offline():
    """Cataloged-but-not-running rows are how the operator UI shows
    "installed but not announcing" without joining client-side."""
    plugin_row = SimpleNamespace(
        oid=uuid.uuid4(),
        name="ctffind4",
        author="Magellon Team",
        category="ctf",
        version="1.0.0",
        schema_version="1",
        manifest_json={"description": "CTF estimator"},
    )
    manager = _build_manager(catalog=[plugin_row])
    [view] = manager.list_installed()
    assert view.plugin_id == "ctf/ctffind4"
    assert view.kind == "broker"
    assert view.description == "CTF estimator"


# ---------------------------------------------------------------------------
# list_running
# ---------------------------------------------------------------------------


def test_list_running_skips_in_process_only_plugins():
    """If a plugin is in the in-process registry but never showed up
    in liveness, it shouldn't appear in ``list_running`` — running
    means "currently announcing on the bus"."""
    manager = _build_manager(
        in_proc=["pp/template-picker"],
        live=[_make_liveness_entry("ctffind4",
                                   manifest=_make_manifest(name="ctffind4"))],
    )
    views = manager.list_running()
    ids = {v.plugin_id for v in views}
    assert ids == {"ctf/ctffind4"}


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_returns_view_for_known_plugin_with_or_without_prefix():
    entry = _make_liveness_entry("ctffind4",
                                 manifest=_make_manifest(name="ctffind4"))
    manager = _build_manager(live=[entry])

    by_short = manager.get("ctffind4")
    by_composed = manager.get("ctf/ctffind4")

    assert by_short is not None
    assert by_composed is not None
    assert by_short.plugin_id == by_composed.plugin_id == "ctf/ctffind4"


def test_get_returns_none_for_unknown_plugin():
    manager = _build_manager(live=[])
    assert manager.get("never-announced") is None


# ---------------------------------------------------------------------------
# status — delegates to PM2's reducer (smoke; full reducer tests in test_plugin_conditions.py)
# ---------------------------------------------------------------------------


def test_status_returns_five_conditions_for_known_plugin():
    """Smoke check: the manager threads liveness + heartbeat into the
    reducer, which emits one Condition per axis. Detailed reducer
    behaviour is covered in test_plugin_conditions.py."""
    entry = _make_liveness_entry("ctffind4",
                                 manifest=_make_manifest(name="ctffind4"))
    manager = _build_manager(live=[entry])

    # The reducer needs a SQLAlchemy session-shaped collaborator.
    # Mirror the four lookups compute_conditions makes for a Live plugin:
    # Plugin row, PluginState, JobEvent rows, Plugin (identity), PCD rows.
    plugin_row = SimpleNamespace(
        oid=uuid.uuid4(),
        name="ctffind4",
        manifest_plugin_id="ctffind4",
    )

    class _Q:
        def __init__(self, r): self._r = r
        def filter(self, *a, **kw): return self
        def join(self, *a, **kw): return self
        def all(self):
            return self._r if isinstance(self._r, list) else (
                [self._r] if self._r is not None else []
            )
        def first(self):
            if isinstance(self._r, list):
                return self._r[0] if self._r else None
            return self._r

    db = MagicMock()
    db.query.side_effect = [
        _Q(plugin_row),    # Plugin
        _Q(None),          # PluginState
        _Q([("completed",)]),  # JobEvent
        _Q(plugin_row),    # Plugin (identity)
        _Q([]),            # PluginCategoryDefault
    ]

    conds = manager.status(db, "ctf/ctffind4")
    types = {c.type for c in conds}
    assert types == {
        ConditionType.INSTALLED,
        ConditionType.ENABLED,
        ConditionType.LIVE,
        ConditionType.HEALTHY,
        ConditionType.DEFAULT,
    }
    healthy = next(c for c in conds if c.type == ConditionType.HEALTHY)
    assert healthy.status is ConditionStatus.TRUE


# ---------------------------------------------------------------------------
# Mutations — pass through to the state store (PM1 write-through under it)
# ---------------------------------------------------------------------------


def test_enable_writes_through_state_store():
    state = _FakeStateStore()
    manager = _build_manager(state=state)
    manager.enable("ctf/ctffind4")
    assert state.set_enabled_calls == [("ctffind4", True)]


def test_disable_writes_through_state_store():
    state = _FakeStateStore()
    manager = _build_manager(state=state)
    manager.disable("ctf/ctffind4")
    assert state.set_enabled_calls == [("ctffind4", False)]


def test_set_default_writes_through_state_store():
    state = _FakeStateStore()
    manager = _build_manager(state=state)
    manager.set_default("ctf", "ctf/ctffind4")
    assert state.set_default_calls == [("ctf", "ctffind4")]


# ---------------------------------------------------------------------------
# PluginView wire shape — pins the contract with the legacy PluginSummary
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# replicas (PM5) — per-replica health
# ---------------------------------------------------------------------------


def test_replicas_classifies_recent_heartbeat_as_healthy():
    now = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    fresh = _make_liveness_entry(
        "ctffind4", instance_id="i-1",
        last_heartbeat=now - timedelta(seconds=5),
    )
    manager = _build_manager(live=[fresh])
    [replica] = manager.replicas("ctf/ctffind4", now=now)
    assert replica.instance_id == "i-1"
    assert replica.status == "Healthy"


def test_replicas_classifies_aged_heartbeat_as_lost():
    """Heartbeat age between healthy_window (30s) and stale_window (60s)
    means the replica missed >2× pulses but hasn't been reaped — call
    it ``Lost`` so the UI's red/amber/green is decisive."""
    now = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    aged = _make_liveness_entry(
        "ctffind4", instance_id="i-2",
        last_heartbeat=now - timedelta(seconds=45),
    )
    manager = _build_manager(live=[aged])
    [replica] = manager.replicas("ctf/ctffind4", now=now)
    assert replica.status == "Lost"


def test_replicas_returns_one_row_per_instance_id():
    """Three live replicas of the same plugin → three rows. Pinned
    because PM5's whole point is exposing per-instance keying — one
    row per ``(plugin_id, instance_id)`` from the registry."""
    now = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    replicas = [
        _make_liveness_entry("ctffind4", instance_id=f"i-{i}",
                             last_heartbeat=now - timedelta(seconds=2))
        for i in range(3)
    ]
    manager = _build_manager(live=replicas)
    rows = manager.replicas("ctf/ctffind4", now=now)
    assert len(rows) == 3
    assert {r.instance_id for r in rows} == {"i-0", "i-1", "i-2"}
    assert all(r.status == "Healthy" for r in rows)


def test_replicas_filters_to_requested_plugin_only():
    now = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    target = _make_liveness_entry("ctffind4", instance_id="i-1",
                                  last_heartbeat=now)
    other = _make_liveness_entry("topaz", instance_id="i-1", category="pp",
                                 last_heartbeat=now)
    manager = _build_manager(live=[target, other])
    rows = manager.replicas("ctffind4", now=now)
    assert len(rows) == 1
    assert rows[0].instance_id == "i-1"


# ---------------------------------------------------------------------------
# list_updates (PM6) — version comparison + cross-reference
# ---------------------------------------------------------------------------


class _FakeCatalogSource:
    def __init__(self, by_slug):
        self._by_slug = by_slug

    def latest_for(self, slug):
        return self._by_slug.get(slug)


def _installed_plugin(name, manifest_plugin_id, version, category="ctf"):
    return SimpleNamespace(
        name=name,
        manifest_plugin_id=manifest_plugin_id,
        version=version,
        category=category,
    )


def test_semver_severity_patch():
    assert _semver_severity("1.0.2", "1.0.5") == "patch"


def test_semver_severity_minor():
    assert _semver_severity("1.0.2", "1.1.0") == "minor"


def test_semver_severity_major():
    assert _semver_severity("1.0.2", "2.0.0") == "major"


def test_semver_severity_returns_none_when_not_newer():
    assert _semver_severity("1.0.2", "1.0.2") is None
    assert _semver_severity("1.0.5", "1.0.2") is None


def test_semver_severity_handles_prerelease_tags():
    """Reviewer-flagged PM6 acceptance: prerelease tags must compare
    as "older than the same version final". 1.2.3-rc.1 < 1.2.3."""
    assert _semver_severity("1.2.3-rc.1", "1.2.3") == "patch"


def test_list_updates_returns_one_row_per_outdated_plugin():
    """End-to-end: PM1's installed catalog × PM6's catalog source."""
    installed = [
        _installed_plugin("CTF Plugin", "ctf", "1.0.2"),
        _installed_plugin("FFT Plugin", "fft", "2.1.0", category="fft"),  # up to date
    ]
    catalog = _FakeCatalogSource({
        "ctf": CatalogVersionInfo(version="1.0.5", archive_url="/cat/ctf-1.0.5.mpn"),
        "fft": CatalogVersionInfo(version="2.1.0"),
    })
    manager = _build_manager(catalog=installed)
    rows = manager.list_updates(catalog_source=catalog)
    assert len(rows) == 1
    assert rows[0].plugin_id == "ctf/CTF Plugin"
    assert rows[0].current_version == "1.0.2"
    assert rows[0].latest_version == "1.0.5"
    assert rows[0].severity == "patch"
    assert rows[0].archive_url == "/cat/ctf-1.0.5.mpn"


def test_list_updates_skips_plugins_missing_from_catalog():
    """A plugin that's installed but the catalog never heard of —
    don't list as updateable. The UI shows it as "no update info."""
    installed = [_installed_plugin("Custom", "custom-impl", "0.1.0")]
    catalog = _FakeCatalogSource({})
    manager = _build_manager(catalog=installed)
    assert manager.list_updates(catalog_source=catalog) == []


# ---------------------------------------------------------------------------
# Wire shape pin
# ---------------------------------------------------------------------------


def test_plugin_view_field_set_matches_legacy_summary():
    """PM3 acceptance: the wire shape must be byte-identical to the
    pre-PM3 PluginSummary. Pin the field set so a future field rename
    here can't silently drift the JSON returned by GET /plugins/."""
    from plugins.controller import PluginSummary
    assert set(PluginView.model_fields) == set(PluginSummary.model_fields)

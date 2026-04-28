"""Tests for ``magellon_sdk.bus.services.liveness_registry``.

Three pieces:

  - :class:`PluginLivenessRegistry` — thread-safe in-memory table
    with announce / heartbeat / list / reap operations
  - process-wide singleton accessor :func:`get_registry`
  - :class:`LivenessListener` + :func:`start_liveness_listener` — the
    bus subscriptions that feed the registry

Tests construct ``Announce`` / ``Heartbeat`` Pydantic objects directly
(no broker required) and exercise every state transition the registry
can be in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from magellon_sdk.bus.services import liveness_registry as lr_mod
from magellon_sdk.bus.services.liveness_registry import (
    LivenessListener,
    PluginLivenessRegistry,
    get_registry,
    start_liveness_listener,
)
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Process-wide singleton — reset so cross-test pollution doesn't
    masquerade as a flaky test."""
    lr_mod._REGISTRY = None
    yield
    lr_mod._REGISTRY = None


def _announce(
    *,
    plugin_id: str = "ctffind4",
    plugin_version: str = "1.0.0",
    instance_id: str | None = None,
    category: str = "ctf",
    manifest=None,
    task_queue: str | None = None,
    backend_id: str | None = None,
    ts: datetime | None = None,
) -> Announce:
    """Build a minimal Announce. ``manifest=None`` is the
    backend-id-fallback path; pass a real manifest to exercise the
    manifest.resolved_backend_id() branch."""
    return Announce(
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        category=category,
        instance_id=instance_id or str(uuid4()),
        manifest=manifest if manifest is not None else _stub_manifest(),
        task_queue=task_queue,
        backend_id=backend_id,
        ts=ts or datetime.now(timezone.utc),
    )


def _stub_manifest():
    """Cheap PluginManifest fixture for tests that don't care about
    its content — just need .resolved_backend_id() to work."""
    from magellon_sdk.models.manifest import PluginManifest
    from magellon_sdk.models.plugin import PluginInfo

    return PluginManifest(
        info=PluginInfo(name="ctffind4", version="1.0.0", developer="t"),
        backend_id="ctffind4",
    )


def _heartbeat(
    *,
    plugin_id: str = "ctffind4",
    plugin_version: str = "1.0.0",
    instance_id: str | None = None,
    category: str = "ctf",
    status: str = "ready",
    ts: datetime | None = None,
) -> Heartbeat:
    return Heartbeat(
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        category=category,
        instance_id=instance_id or str(uuid4()),
        status=status,
        ts=ts or datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# record_announce
# ---------------------------------------------------------------------------

def test_record_announce_creates_entry_with_manifest():
    reg = PluginLivenessRegistry()
    msg = _announce()

    reg.record_announce(msg)

    snap = reg.snapshot()
    assert len(snap) == 1
    assert snap[0]["plugin_id"] == "ctffind4"
    assert snap[0]["category"] == "ctf"


def test_record_announce_falls_back_to_manifest_backend_id():
    """SDK 1.3+ sends backend_id explicitly. SDK 1.2 / pre-1.3 sends
    only the manifest; the registry must derive backend_id from
    manifest.resolved_backend_id() to keep the dispatcher's pinning
    path working."""
    reg = PluginLivenessRegistry()
    msg = _announce(backend_id=None)  # no explicit backend_id

    reg.record_announce(msg)

    entry = reg.snapshot()[0]
    assert entry["backend_id"] == "ctffind4"


def test_record_announce_falls_back_to_slugged_plugin_id_when_manifest_missing():
    """If both backend_id and manifest.resolved_backend_id() are
    unavailable (very old plugin or malformed manifest), the registry
    slugs the plugin_id so something matches. Without this fallback
    the entry would have backend_id=None and target_backend pinning
    couldn't reach the plugin."""
    reg = PluginLivenessRegistry()
    msg = Announce(
        plugin_id="My CTF Plugin",
        plugin_version="0.1.0",
        category="ctf",
        instance_id=str(uuid4()),
        manifest=_stub_manifest(),
        backend_id=None,
    )
    # Force the manifest fallback to fail by clobbering the helper.
    object.__setattr__(
        msg.manifest, "resolved_backend_id",
        lambda: (_ for _ in ()).throw(RuntimeError("malformed")),
    )

    reg.record_announce(msg)

    entry = reg.snapshot()[0]
    # Slug: lowercase + replace whitespace with '-'
    assert entry["backend_id"] == "my-ctf-plugin"


def test_record_announce_updates_existing_entry():
    """Re-announce on plugin reconnect: same (plugin_id, instance_id)
    must update the existing entry's manifest + version + heartbeat,
    not create a duplicate."""
    reg = PluginLivenessRegistry()
    instance = str(uuid4())
    reg.record_announce(_announce(plugin_version="1.0.0", instance_id=instance))
    reg.record_announce(_announce(plugin_version="1.0.1", instance_id=instance))

    snap = reg.snapshot()
    assert len(snap) == 1
    assert snap[0]["plugin_version"] == "1.0.1"


def test_record_announce_preserves_task_queue_when_reannounce_omits_it():
    """Pre-SDK-1.1 plugins re-announce without task_queue. The
    registry must NOT clobber the queue learned from the first
    announce — that would break the dispatcher's routing on the
    second tick."""
    reg = PluginLivenessRegistry()
    instance = str(uuid4())
    reg.record_announce(_announce(instance_id=instance, task_queue="custom_q"))
    reg.record_announce(_announce(instance_id=instance, task_queue=None))

    assert reg.snapshot()[0]["task_queue"] == "custom_q"


# ---------------------------------------------------------------------------
# DUP_BACKEND_ID warning
# ---------------------------------------------------------------------------

def test_warn_duplicate_backend_when_two_plugins_collide(caplog):
    """Two distinct plugin_ids in the same category claiming the same
    backend_id is a misconfiguration the operator must see. The
    dispatcher will route to whichever it finds first, which is the
    bug to surface, not silently accept."""
    reg = PluginLivenessRegistry()
    reg.record_announce(_announce(
        plugin_id="ctffind4-classic", backend_id="ctffind4",
    ))

    with caplog.at_level("WARNING"):
        reg.record_announce(_announce(
            plugin_id="ctffind4-fork", backend_id="ctffind4",
        ))

    assert any("DUP_BACKEND_ID" in r.message for r in caplog.records)


def test_no_warn_when_same_plugin_id_replicas_share_backend(caplog):
    """Same plugin_id under different instance_ids = scale-out
    replicas of the same backend. NOT a collision; must not log."""
    reg = PluginLivenessRegistry()
    reg.record_announce(_announce(plugin_id="ctffind4", backend_id="ctffind4"))

    with caplog.at_level("WARNING"):
        reg.record_announce(_announce(plugin_id="ctffind4", backend_id="ctffind4"))

    assert not any("DUP_BACKEND_ID" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# record_heartbeat
# ---------------------------------------------------------------------------

def test_record_heartbeat_updates_existing_entry():
    """The hot path — a plugin that announced earlier sends pulses;
    each updates last_heartbeat + status without rebuilding the entry."""
    reg = PluginLivenessRegistry()
    instance = str(uuid4())
    reg.record_announce(_announce(instance_id=instance))
    later = datetime.now(timezone.utc) + timedelta(seconds=30)
    reg.record_heartbeat(_heartbeat(
        instance_id=instance, status="busy", ts=later,
    ))

    entry = reg.snapshot()[0]
    assert entry["status"] == "busy"
    assert entry["last_heartbeat"] == later.isoformat()


def test_record_heartbeat_creates_stub_when_no_announce_yet():
    """Heartbeat-before-announce can happen during CoreService
    restart: the plugin keeps pulsing but the announce we're listening
    for happened before we subscribed. Without this stub, the plugin
    would stay invisible until its next restart. The next announce
    fills in the manifest."""
    reg = PluginLivenessRegistry()
    reg.record_heartbeat(_heartbeat(plugin_id="ctffind4"))

    snap = reg.snapshot()
    assert len(snap) == 1
    assert snap[0]["plugin_id"] == "ctffind4"
    # backend_id is best-guessed from plugin_id slug.
    assert snap[0]["backend_id"] == "ctffind4"


# ---------------------------------------------------------------------------
# list_live + reap_stale
# ---------------------------------------------------------------------------

def test_list_live_filters_out_entries_past_stale_window():
    """A plugin that stopped pulsing 90s ago shouldn't appear as
    live. The 60s default cutoff is 4× the default heartbeat
    interval — three missed pulses before we hide it."""
    reg = PluginLivenessRegistry(stale_after_seconds=60.0)
    now = datetime.now(timezone.utc)
    reg.record_announce(_announce(plugin_id="fresh", ts=now))
    reg.record_announce(_announce(
        plugin_id="stale", ts=now - timedelta(seconds=90),
    ))

    live = reg.list_live(now=now)

    assert {e.plugin_id for e in live} == {"fresh"}


def test_reap_stale_removes_entries_past_window():
    """list_live filters but keeps entries; reap_stale actually
    deletes them so the table doesn't grow unboundedly across
    plugin restarts."""
    reg = PluginLivenessRegistry(stale_after_seconds=60.0)
    now = datetime.now(timezone.utc)
    reg.record_announce(_announce(
        plugin_id="goner", ts=now - timedelta(seconds=120),
    ))
    reg.record_announce(_announce(plugin_id="alive", ts=now))

    removed = reg.reap_stale(now=now)

    assert removed == 1
    assert {e["plugin_id"] for e in reg.snapshot()} == {"alive"}


def test_reap_stale_handles_entries_with_no_heartbeat():
    """A stub entry created by record_heartbeat-before-announce has
    last_heartbeat set; but a hypothetical entry with None must also
    reap correctly. Defensive: the check is `or last_heartbeat <
    cutoff`, so None reaps too."""
    reg = PluginLivenessRegistry(stale_after_seconds=60.0)
    reg.record_announce(_announce(plugin_id="x"))
    # Force last_heartbeat=None on the entry.
    list(reg._entries.values())[0].last_heartbeat = None

    removed = reg.reap_stale()

    assert removed == 1
    assert reg.snapshot() == []


# ---------------------------------------------------------------------------
# get_registry singleton
# ---------------------------------------------------------------------------

def test_get_registry_lazy_constructs_singleton():
    a = get_registry()
    b = get_registry()
    assert a is b
    assert isinstance(a, PluginLivenessRegistry)


# ---------------------------------------------------------------------------
# LivenessListener.stop
# ---------------------------------------------------------------------------

def test_listener_stop_closes_both_handles():
    """Both subscriptions must be released on shutdown — leaking
    one is observable as a dangling subscriber count on the broker
    UI and a phantom DLQ-route delivery on the next restart."""
    announce_handle = MagicMock()
    heartbeat_handle = MagicMock()
    listener = LivenessListener(
        registry=PluginLivenessRegistry(),
        announce_handle=announce_handle,
        heartbeat_handle=heartbeat_handle,
    )

    listener.stop()

    announce_handle.close.assert_called_once()
    heartbeat_handle.close.assert_called_once()


def test_listener_stop_continues_when_one_handle_close_fails():
    """If announce.close() raises, heartbeat.close() must still run
    — process shutdown shouldn't be blocked by one stuck subscription."""
    announce_handle = MagicMock()
    announce_handle.close.side_effect = RuntimeError("subscription gone")
    heartbeat_handle = MagicMock()
    listener = LivenessListener(
        registry=PluginLivenessRegistry(),
        announce_handle=announce_handle,
        heartbeat_handle=heartbeat_handle,
    )

    # Should not raise.
    listener.stop()

    heartbeat_handle.close.assert_called_once()


# ---------------------------------------------------------------------------
# start_liveness_listener
# ---------------------------------------------------------------------------

def test_start_liveness_listener_subscribes_to_both_routes():
    """The listener subscribes once for announce, once for heartbeat —
    not one wildcard binding. Pre-MB5.4a the wildcard pulled in
    config-broker messages on the same exchange; the explicit
    subscriptions fix that."""
    bus = MagicMock()
    reg = PluginLivenessRegistry()

    listener = start_liveness_listener(registry=reg, bus=bus)

    assert bus.events.subscribe.call_count == 2
    patterns = [c.args[0].subject_glob for c in bus.events.subscribe.call_args_list]
    assert "magellon.plugins.announce.>" in patterns
    assert "magellon.plugins.heartbeat.>" in patterns
    assert isinstance(listener, LivenessListener)


def test_start_liveness_listener_decodes_announce_envelope():
    """The handler must unwrap the envelope's data field into an
    Announce model. A regression that handed envelope.data straight
    to record_announce would crash on dict access — pin the decode."""
    bus = MagicMock()
    reg = PluginLivenessRegistry()
    start_liveness_listener(registry=reg, bus=bus)

    # First call.args.args is (pattern, handler) for the announce route.
    announce_handler = bus.events.subscribe.call_args_list[0].args[1]
    msg = _announce(plugin_id="from-bus")
    env = Envelope.wrap(
        source="t", type="m", subject="x",
        data=msg.model_dump(mode="json"),
    )

    announce_handler(env)

    assert reg.snapshot()[0]["plugin_id"] == "from-bus"


def test_start_liveness_listener_decodes_heartbeat_envelope():
    bus = MagicMock()
    reg = PluginLivenessRegistry()
    start_liveness_listener(registry=reg, bus=bus)

    heartbeat_handler = bus.events.subscribe.call_args_list[1].args[1]
    msg = _heartbeat(plugin_id="hb-only")
    env = Envelope.wrap(
        source="t", type="m", subject="x",
        data=msg.model_dump(mode="json"),
    )

    heartbeat_handler(env)

    # Stub entry created (no announce).
    assert reg.snapshot()[0]["plugin_id"] == "hb-only"


def test_start_liveness_listener_raises_permanent_on_bad_announce():
    """A malformed announce envelope (someone published the wrong
    schema) must DLQ, not requeue forever. Raising PermanentError
    routes it cleanly via classify_exception."""
    bus = MagicMock()
    start_liveness_listener(bus=bus)
    announce_handler = bus.events.subscribe.call_args_list[0].args[1]

    bad_env = Envelope.wrap(
        source="t", type="m", subject="x",
        data={"not": "valid"},
    )

    with pytest.raises(PermanentError):
        announce_handler(bad_env)


def test_start_liveness_listener_raises_permanent_on_bad_heartbeat():
    bus = MagicMock()
    start_liveness_listener(bus=bus)
    heartbeat_handler = bus.events.subscribe.call_args_list[1].args[1]

    with pytest.raises(PermanentError):
        heartbeat_handler(Envelope.wrap(
            source="t", type="m", subject="x", data={"junk": True},
        ))


def test_start_liveness_listener_uses_default_registry_when_none_passed():
    """Mirrors get_registry(); plugin authors call this with no args
    and get the singleton fed automatically."""
    bus = MagicMock()
    listener = start_liveness_listener(bus=bus)
    assert listener.registry is get_registry()

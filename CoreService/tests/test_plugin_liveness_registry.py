"""Tests for the broker-fed plugin liveness registry (P6).

These pin the *table* invariants — the broker side is tested in the
SDK. Here we make sure:

  - Announce + heartbeat round-trip into entries keyed by
    (plugin_id, instance_id).
  - A heartbeat that beats the announce home doesn't drop the plugin
    on the floor — we materialize a stub.
  - Stale entries (no heartbeat within the window) drop out of
    list_live() and reap_stale() removes them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core import plugin_liveness_registry as liveness_mod
from core.plugin_liveness_registry import PluginLivenessRegistry
from magellon_sdk.envelope import Envelope
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.models.manifest import (
    Capability,
    PluginManifest,
    Transport,
)
from magellon_sdk.models.plugin import PluginInfo


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _manifest() -> PluginManifest:
    return PluginManifest(
        info=PluginInfo(name="ctf-ctffind", version="4.1.14", developer="t"),
        capabilities=[Capability.CPU_INTENSIVE],
        supported_transports=[Transport.RMQ],
    )


def _announce(**kwargs):
    defaults = dict(
        plugin_id="ctf-ctffind",
        plugin_version="4.1.14",
        category="ctf",
        instance_id="i-1",
        manifest=_manifest(),
    )
    defaults.update(kwargs)
    return Announce(**defaults)


def _heartbeat(**kwargs):
    defaults = dict(
        plugin_id="ctf-ctffind",
        plugin_version="4.1.14",
        category="ctf",
        instance_id="i-1",
    )
    defaults.update(kwargs)
    return Heartbeat(**defaults)


def test_announce_creates_entry_with_manifest():
    reg = PluginLivenessRegistry()
    reg.record_announce(_announce())

    live = reg.list_live()
    assert len(live) == 1
    assert live[0].plugin_id == "ctf-ctffind"
    assert live[0].manifest.info.name == "ctf-ctffind"


def test_heartbeat_updates_existing_entry():
    reg = PluginLivenessRegistry()
    reg.record_announce(_announce())
    later = _now() + timedelta(seconds=5)
    reg.record_heartbeat(_heartbeat(ts=later, status="busy"))

    live = reg.list_live()
    assert len(live) == 1
    assert live[0].status == "busy"
    assert live[0].last_heartbeat == later


def test_heartbeat_before_announce_creates_stub():
    """A CoreService that came up after the plugin missed the
    announce. The next heartbeat must still register the plugin —
    otherwise ops can't see it until the plugin restarts."""
    reg = PluginLivenessRegistry()
    reg.record_heartbeat(_heartbeat())

    live = reg.list_live()
    assert len(live) == 1
    assert live[0].plugin_id == "ctf-ctffind"
    assert live[0].manifest is None  # stub — manifest filled in on next announce


def test_two_replicas_of_same_plugin_are_distinct():
    """Two containers of the same plugin must show up as separate
    rows so an operator can spot which one is misbehaving. The
    instance_id is what makes them distinguishable."""
    reg = PluginLivenessRegistry()
    reg.record_announce(_announce(instance_id="i-1"))
    reg.record_announce(_announce(instance_id="i-2"))

    live = reg.list_live()
    instance_ids = sorted(e.instance_id for e in live)
    assert instance_ids == ["i-1", "i-2"]


def test_stale_entries_drop_out_of_list_live():
    reg = PluginLivenessRegistry(stale_after_seconds=10.0)
    old_ts = _now() - timedelta(seconds=60)
    reg.record_heartbeat(_heartbeat(ts=old_ts))

    assert reg.list_live() == []


def test_reap_stale_removes_old_entries_and_returns_count():
    reg = PluginLivenessRegistry(stale_after_seconds=10.0)
    reg.record_heartbeat(_heartbeat(instance_id="old", ts=_now() - timedelta(seconds=60)))
    reg.record_heartbeat(_heartbeat(instance_id="new", ts=_now()))

    removed = reg.reap_stale()
    assert removed == 1
    snapshot = reg.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["instance_id"] == "new"


class _Handle:
    def close(self):
        return None


class _Events:
    def __init__(self):
        self.handlers = []

    def subscribe(self, route, handler):
        self.handlers.append(handler)
        return _Handle()


class _Bus:
    def __init__(self):
        self.events = _Events()


def test_liveness_listener_persists_announce_and_heartbeat(monkeypatch):
    """CoreService's wrapper keeps the SDK in-memory registry behavior
    and also mirrors discovery into the DB-backed catalog."""
    persisted_announces = []
    persisted_heartbeats = []
    monkeypatch.setattr(liveness_mod, "persist_announce", persisted_announces.append)
    monkeypatch.setattr(liveness_mod, "persist_heartbeat", persisted_heartbeats.append)

    bus = _Bus()
    reg = PluginLivenessRegistry()
    liveness_mod.start_liveness_listener(registry=reg, bus=bus)

    announce = _announce()
    heartbeat = _heartbeat(status="busy")
    bus.events.handlers[0](
        Envelope.wrap(source="test", type="a", subject="announce", data=announce)
    )
    bus.events.handlers[1](
        Envelope.wrap(source="test", type="h", subject="heartbeat", data=heartbeat)
    )

    assert persisted_announces == [announce]
    assert persisted_heartbeats == [heartbeat]
    live = reg.list_live()
    assert len(live) == 1
    assert live[0].status == "busy"

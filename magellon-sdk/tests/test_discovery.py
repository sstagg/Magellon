"""Tests for broker-based discovery + heartbeat (P6).

The broker IS the registration mechanism — these tests pin the wire
contracts a CoreService listener (or any other consumer) can rely on:

  - Announce + Heartbeat both round-trip through JSON.
  - Subjects derive from the category contract (no per-plugin strings).
  - HeartbeatLoop publishes immediately on start, and stops cleanly.
  - Publisher swallows broker errors so a transient outage can't take
    the plugin's main consumer down.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.categories.contract import CTF, announce_subject, heartbeat_subject
from magellon_sdk.discovery import (
    Announce,
    DiscoveryPublisher,
    Heartbeat,
    HeartbeatLoop,
)
from magellon_sdk.models.manifest import (
    Capability,
    PluginManifest,
    Transport,
)
from magellon_sdk.models.plugin import PluginInfo


def _make_manifest() -> PluginManifest:
    return PluginManifest(
        info=PluginInfo(name="ctf-ctffind", version="4.1.14", developer="t"),
        capabilities=[Capability.CPU_INTENSIVE],
        supported_transports=[Transport.RMQ],
        default_transport=Transport.RMQ,
    )


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------

def test_announce_round_trips_through_json():
    """Announce has to deserialize identically on the listener side —
    that's the contract the liveness registry depends on."""
    msg = Announce(
        plugin_id="ctf-ctffind",
        plugin_version="4.1.14",
        category="ctf",
        manifest=_make_manifest(),
    )
    restored = Announce.model_validate_json(msg.model_dump_json())
    assert restored.plugin_id == "ctf-ctffind"
    assert restored.manifest.info.name == "ctf-ctffind"
    assert restored.instance_id == msg.instance_id


def test_heartbeat_round_trips_through_json():
    """Heartbeats are emitted on a timer — wire shape stability matters
    even more than for announce because there are 100x more of them."""
    msg = Heartbeat(plugin_id="ctf-ctffind", plugin_version="4.1.14", category="ctf")
    restored = Heartbeat.model_validate_json(msg.model_dump_json())
    assert restored.plugin_id == "ctf-ctffind"
    assert restored.status == "ready"


def test_announce_and_heartbeat_distinguishable_by_manifest_key():
    """The CoreService listener routes Announce vs Heartbeat by checking
    if 'manifest' is present in the JSON. Pin that the wire shapes
    actually differ on that key, so the dispatch rule isn't fragile."""
    a = Announce(
        plugin_id="x",
        plugin_version="1",
        category="ctf",
        manifest=_make_manifest(),
    ).model_dump()
    h = Heartbeat(plugin_id="x", plugin_version="1", category="ctf").model_dump()
    assert "manifest" in a and a["manifest"] is not None
    assert "manifest" not in h


# ---------------------------------------------------------------------------
# Subject naming
# ---------------------------------------------------------------------------

def test_announce_subject_uses_category_and_plugin_lowercased():
    """Operators wildcard-bind on these — ``magellon.plugins.announce.ctf.*``
    has to match every CTF plugin's announce. Pin the shape."""
    assert announce_subject("CTF", "ctf-ctffind") == "magellon.plugins.announce.ctf.ctf-ctffind"
    assert heartbeat_subject("CTF", "ctf-ctffind") == "magellon.plugins.heartbeat.ctf.ctf-ctffind"


# ---------------------------------------------------------------------------
# Publisher behavior
# ---------------------------------------------------------------------------

def test_publisher_swallows_broker_errors_so_plugin_loop_survives():
    """A broker hiccup at announce/heartbeat time must not raise into
    the plugin — discovery is best-effort, not part of correctness."""
    pub = DiscoveryPublisher(settings=MagicMock())

    with patch.object(pub, "_ensure_open", side_effect=RuntimeError("broker down")):
        # Should not raise.
        pub.heartbeat(CTF, Heartbeat(plugin_id="x", plugin_version="1", category="ctf"))
        pub.announce(CTF, Announce(
            plugin_id="x", plugin_version="1", category="ctf", manifest=_make_manifest()
        ))


def test_publisher_routes_to_correct_subject():
    """Announce → announce.<cat>.<plugin>; heartbeat → heartbeat.<cat>.<plugin>.
    The subject is what every consumer binds on; getting it wrong
    silently strands the message."""
    pub = DiscoveryPublisher(settings=MagicMock())
    pub._channel = MagicMock()
    pub._connection = MagicMock()
    pub._connection.is_closed = False

    pub.heartbeat(CTF, Heartbeat(plugin_id="ctf-ctffind", plugin_version="1", category="ctf"))
    pub.announce(CTF, Announce(
        plugin_id="ctf-ctffind",
        plugin_version="1",
        category="ctf",
        manifest=_make_manifest(),
    ))

    routing_keys = [
        call.kwargs["routing_key"] for call in pub._channel.basic_publish.call_args_list
    ]
    assert "magellon.plugins.heartbeat.ctf.ctf-ctffind" in routing_keys
    assert "magellon.plugins.announce.ctf.ctf-ctffind" in routing_keys


# ---------------------------------------------------------------------------
# HeartbeatLoop
# ---------------------------------------------------------------------------

def test_heartbeat_loop_pulses_immediately_on_start():
    """Without an immediate first pulse, a manager waits a full
    interval before noticing the plugin — too slow for ops."""
    pub = MagicMock()
    loop = HeartbeatLoop(
        publisher=pub,
        contract=CTF,
        plugin_id="ctf-ctffind",
        plugin_version="1",
        instance_id="abc",
        interval_seconds=10.0,  # large so we don't depend on a second tick
    )
    loop.start()
    # Give the daemon thread a moment to fire the first pulse.
    for _ in range(50):
        if pub.heartbeat.called:
            break
        time.sleep(0.01)
    loop.stop()
    assert pub.heartbeat.called


def test_heartbeat_loop_stops_cleanly():
    """Calling stop() must end the loop quickly — a slow shutdown
    holds the plugin process from exiting."""
    pub = MagicMock()
    loop = HeartbeatLoop(
        publisher=pub,
        contract=CTF,
        plugin_id="x",
        plugin_version="1",
        instance_id="i",
        interval_seconds=60.0,  # would block forever if stop() didn't break it
    )
    loop.start()
    time.sleep(0.05)
    loop.stop()
    loop._thread.join(timeout=2.0)
    assert not loop._thread.is_alive()

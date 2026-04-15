"""Tests for broker-based dynamic configuration (P7).

The contract these pin:

  - ConfigUpdate round-trips through JSON (the wire shape every
    subscriber depends on).
  - Publisher routes category vs broadcast to the right subjects, so
    a category push doesn't accidentally touch every plugin.
  - Publisher swallows broker errors so a hiccup at config-push time
    doesn't crash whatever called it (CoreService API handler, ops
    CLI, etc.).
  - Subscriber buffers + drains correctly: take_pending merges
    last-write-wins, returns None on idle, and drops out-of-order
    versions.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.categories.contract import (
    CONFIG_BROADCAST_SUBJECT,
    CTF,
    config_subject,
)
from magellon_sdk.config_broker import (
    ConfigPublisher,
    ConfigSubscriber,
    ConfigUpdate,
)


# ---------------------------------------------------------------------------
# Wire shape
# ---------------------------------------------------------------------------

def test_config_update_round_trips_through_json():
    """The subscriber reads JSON off the wire — model_validate_json
    must reconstruct the same object the publisher serialized."""
    msg = ConfigUpdate(
        target="ctf",
        settings={"gpfs_root": "/data/v2", "max_resolution": 4.5},
        version=7,
    )
    restored = ConfigUpdate.model_validate_json(msg.model_dump_json())
    assert restored.target == "ctf"
    assert restored.settings["gpfs_root"] == "/data/v2"
    assert restored.settings["max_resolution"] == 4.5
    assert restored.version == 7


def test_config_update_version_optional_for_simple_pushes():
    """The single-publisher case shouldn't have to invent a version
    just to make the type happy."""
    msg = ConfigUpdate(target="broadcast", settings={"log_level": "DEBUG"})
    assert msg.version is None


# ---------------------------------------------------------------------------
# Publisher routing
# ---------------------------------------------------------------------------

def test_publisher_routes_category_push_to_category_subject():
    """A CTF-only setting must not land on the broadcast subject —
    that would push CTF knobs onto motioncor plugins."""
    pub = ConfigPublisher(settings=MagicMock())
    pub._channel = MagicMock()
    pub._connection = MagicMock()
    pub._connection.is_closed = False

    pub.publish_to_category(CTF, {"max_res": 4.5})

    call = pub._channel.basic_publish.call_args
    assert call.kwargs["routing_key"] == config_subject("CTF")


def test_publisher_routes_broadcast_to_broadcast_subject():
    pub = ConfigPublisher(settings=MagicMock())
    pub._channel = MagicMock()
    pub._connection = MagicMock()
    pub._connection.is_closed = False

    pub.publish_broadcast({"log_level": "INFO"})

    call = pub._channel.basic_publish.call_args
    assert call.kwargs["routing_key"] == CONFIG_BROADCAST_SUBJECT


def test_publisher_swallows_broker_errors():
    """A broker hiccup at config-push time must not raise into the
    caller — the operator CLI / API handler shouldn't 500 because the
    broker happens to be bouncing."""
    pub = ConfigPublisher(settings=MagicMock())
    with patch.object(pub, "_ensure_open", side_effect=RuntimeError("broker down")):
        # Should not raise.
        pub.publish_to_category(CTF, {"x": 1})
        pub.publish_broadcast({"y": 2})


# ---------------------------------------------------------------------------
# Subscriber buffering
# ---------------------------------------------------------------------------

def test_subscriber_take_pending_returns_none_when_idle():
    """The harness calls this every delivery — returning None lets it
    skip the configure() call instead of churning through a no-op."""
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    assert sub.take_pending() is None


def test_subscriber_buffers_then_drains_in_one_shot():
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    sub.deliver(ConfigUpdate(target="ctf", settings={"a": 1, "b": 2}))

    drained = sub.take_pending()
    assert drained == {"a": 1, "b": 2}
    # Second drain in a row sees nothing — buffer cleared.
    assert sub.take_pending() is None


def test_subscriber_merges_last_write_wins_within_buffer():
    """Two pushes between drains: the later value for any key wins.
    This matches the way CoreService is expected to publish — the
    most recent push reflects current intent."""
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    sub.deliver(ConfigUpdate(target="ctf", settings={"a": 1, "b": 2}))
    sub.deliver(ConfigUpdate(target="ctf", settings={"b": 99, "c": 3}))

    drained = sub.take_pending()
    assert drained == {"a": 1, "b": 99, "c": 3}


def test_subscriber_drops_out_of_order_versions():
    """If a publisher emits versioned updates and a later one arrives
    first (broker reorder), the older one must be dropped — otherwise
    we'd quietly roll a setting backwards."""
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    sub.deliver(ConfigUpdate(target="ctf", settings={"k": "new"}, version=5))
    # An older delivery showing up late.
    sub.deliver(ConfigUpdate(target="ctf", settings={"k": "old"}, version=3))

    drained = sub.take_pending()
    assert drained == {"k": "new"}


def test_subscriber_unversioned_updates_always_apply():
    """Versioning is opt-in — an unversioned stream is "trust the
    broker order" and every update goes through."""
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    sub.deliver(ConfigUpdate(target="ctf", settings={"k": "first"}))
    sub.deliver(ConfigUpdate(target="ctf", settings={"k": "second"}))

    drained = sub.take_pending()
    assert drained == {"k": "second"}

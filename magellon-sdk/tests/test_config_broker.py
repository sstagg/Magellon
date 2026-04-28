"""Tests for broker-based dynamic configuration (P7 + persistence).

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
  - Persistent pushes (``ConfigUpdate.persistent=True``) get written
    to disk by subscribers configured with a path, and reloaded into
    the buffer on boot — so a plugin restart preserves the operator's
    last persistent push.
"""
from __future__ import annotations

import json
from pathlib import Path
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
    that would push CTF knobs onto motioncor plugins. Post-MB5.2 the
    route is ConfigRoute.for_category(contract) whose subject string
    is ``magellon.plugins.config.ctf``."""
    bus = MagicMock()
    pub = ConfigPublisher(bus=bus)

    pub.publish_to_category(CTF, {"max_res": 4.5})

    bus.events.publish.assert_called_once()
    route, envelope = bus.events.publish.call_args.args
    assert route.subject == config_subject("CTF")
    # Envelope wraps the ConfigUpdate so the wire body stays
    # identical (CloudEvents binary content mode).
    assert envelope.data.target == "ctf"
    assert envelope.data.settings == {"max_res": 4.5}


def test_publisher_routes_broadcast_to_broadcast_subject():
    bus = MagicMock()
    pub = ConfigPublisher(bus=bus)

    pub.publish_broadcast({"log_level": "INFO"})

    bus.events.publish.assert_called_once()
    route, envelope = bus.events.publish.call_args.args
    assert route.subject == CONFIG_BROADCAST_SUBJECT
    assert envelope.data.target == "broadcast"


def test_publisher_swallows_broker_errors():
    """A broker hiccup at config-push time must not raise into the
    caller — the operator CLI / API handler shouldn't 500 because the
    broker happens to be bouncing. Post-MB5.2 the publisher catches
    anything bus.events.publish raises."""
    bus = MagicMock()
    bus.events.publish.side_effect = RuntimeError("broker down")
    pub = ConfigPublisher(bus=bus)

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


# ---------------------------------------------------------------------------
# Persistence (the ``persistent`` flag)
# ---------------------------------------------------------------------------

def test_config_update_persistent_defaults_false():
    """Backwards compat: existing publishers don't set the flag, so
    the default must be False — otherwise live pushes would start
    writing files unexpectedly."""
    msg = ConfigUpdate(target="ctf", settings={"x": 1})
    assert msg.persistent is False


def test_config_update_persistent_round_trips_through_json():
    """The flag travels in the JSON payload like every other field."""
    msg = ConfigUpdate(target="ctf", settings={"x": 1}, persistent=True)
    restored = ConfigUpdate.model_validate_json(msg.model_dump_json())
    assert restored.persistent is True


def test_publisher_passes_persistent_flag_through():
    bus = MagicMock()
    pub = ConfigPublisher(bus=bus)

    pub.publish_to_category(CTF, {"max_res": 4.5}, persistent=True)
    pub.publish_broadcast({"log_level": "DEBUG"}, persistent=True)

    assert bus.events.publish.call_count == 2
    cat_envelope = bus.events.publish.call_args_list[0].args[1]
    bcast_envelope = bus.events.publish.call_args_list[1].args[1]
    assert cat_envelope.data.persistent is True
    assert bcast_envelope.data.persistent is True


def test_subscriber_without_path_ignores_persistent_flag(tmp_path):
    """A subscriber not configured with a persisted_path should still
    accept a persistent push (apply in-memory) and never touch the
    filesystem. We verify by giving tmp_path but NOT passing it to
    the subscriber — if anything got written we'd see a file."""
    sub = ConfigSubscriber(settings=MagicMock(), contract=CTF)
    sub.deliver(ConfigUpdate(target="ctf", settings={"x": 1}, persistent=True))

    assert sub.take_pending() == {"x": 1}
    # tmp_path is empty — no file leaked through.
    assert list(tmp_path.iterdir()) == []


def test_subscriber_does_not_write_for_non_persistent_push(tmp_path):
    """Persistence is opt-in per message — a normal push must not
    create a file even when the path is configured."""
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    sub.deliver(ConfigUpdate(target="ctf", settings={"x": 1}))  # persistent=False (default)

    assert sub.take_pending() == {"x": 1}
    assert not persisted.exists()


def test_subscriber_writes_for_persistent_push(tmp_path):
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    sub.deliver(ConfigUpdate(target="ctf", settings={"max_res": 4.5}, persistent=True))

    assert persisted.exists()
    saved = json.loads(persisted.read_text())
    assert saved == {"max_res": 4.5}


def test_subscriber_writes_to_nested_directory(tmp_path):
    """Per-plugin layouts often want a category subdirectory; the
    subscriber must mkdir parents so the operator doesn't have to
    pre-create the path."""
    persisted = tmp_path / "magellon" / "config" / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    sub.deliver(ConfigUpdate(target="ctf", settings={"k": "v"}, persistent=True))

    assert persisted.exists()


def test_subscriber_persisted_state_accumulates(tmp_path):
    """Multiple persistent pushes merge into one file (last-write-wins
    per key, like in-memory). A non-persistent push between them
    must NOT pollute the persisted snapshot."""
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    sub.deliver(ConfigUpdate(target="ctf", settings={"a": 1}, persistent=True))
    sub.deliver(ConfigUpdate(target="ctf", settings={"b": 2}))                        # not persistent
    sub.deliver(ConfigUpdate(target="ctf", settings={"a": 99, "c": 3}, persistent=True))

    saved = json.loads(persisted.read_text())
    assert saved == {"a": 99, "c": 3}  # 'b' was non-persistent, must not appear


def test_subscriber_loads_persisted_state_on_construction(tmp_path):
    """The whole point: on boot, the subscriber primes _pending so
    the runner's first take_pending() returns the values the
    operator pushed last week."""
    persisted = tmp_path / "ctf.json"
    persisted.write_text(json.dumps({"max_res": 4.5, "iterations": 7}))

    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    drained = sub.take_pending()
    assert drained == {"max_res": 4.5, "iterations": 7}


def test_subscriber_load_then_persistent_push_merges(tmp_path):
    """Persisted state at boot + a new persistent push during runtime
    should both end up on disk after the push — the new push merges
    on top of what was loaded."""
    persisted = tmp_path / "ctf.json"
    persisted.write_text(json.dumps({"a": 1, "b": 2}))

    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    sub.take_pending()  # drain the loaded state to simulate apply

    sub.deliver(ConfigUpdate(target="ctf", settings={"b": 99}, persistent=True))

    saved = json.loads(persisted.read_text())
    assert saved == {"a": 1, "b": 99}


def test_subscriber_handles_missing_persisted_file(tmp_path):
    """A fresh deployment has no persisted file — boot must succeed
    silently with empty state."""
    persisted = tmp_path / "does_not_exist.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    assert sub.take_pending() is None


def test_subscriber_handles_malformed_persisted_file(tmp_path, caplog):
    """A corrupted file (truncated, hand-edited badly) must not crash
    plugin boot. The subscriber logs and moves on with empty state."""
    persisted = tmp_path / "ctf.json"
    persisted.write_text("{not valid json")

    with caplog.at_level("WARNING"):
        sub = ConfigSubscriber(
            settings=MagicMock(), contract=CTF, persisted_path=persisted,
        )

    assert sub.take_pending() is None
    assert any("not valid JSON" in r.message for r in caplog.records)


def test_subscriber_handles_persisted_file_not_a_dict(tmp_path, caplog):
    """Defensive: someone hand-wrote a JSON list or scalar. Same
    behavior as malformed — log + start empty."""
    persisted = tmp_path / "ctf.json"
    persisted.write_text("[1, 2, 3]")

    with caplog.at_level("WARNING"):
        sub = ConfigSubscriber(
            settings=MagicMock(), contract=CTF, persisted_path=persisted,
        )

    assert sub.take_pending() is None
    assert any("not a JSON object" in r.message for r in caplog.records)


def test_subscriber_atomic_write_leaves_no_tmp_on_success(tmp_path):
    """Atomic write uses a .tmp sibling that gets renamed on success.
    After a successful write, no .tmp file should remain — any
    leftover is evidence of a write that failed mid-flight."""
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )

    sub.deliver(ConfigUpdate(target="ctf", settings={"x": 1}, persistent=True))

    # Final file exists, no .tmp leftover.
    assert persisted.exists()
    assert not (tmp_path / "ctf.json.tmp").exists()

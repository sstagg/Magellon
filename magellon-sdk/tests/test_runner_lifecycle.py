"""Tests for ``magellon_sdk.runner.lifecycle`` — gap #2 from the
coverage audit.

The lifecycle helpers live below ``PluginBrokerRunner`` and own:

  - building / starting the discovery publisher + heartbeat loop
    (idempotent across reconnects via the ``existing_*`` parameters)
  - creating + starting the config subscriber, plumbing the
    ``persisted_path`` through

The audit flagged ``runner/lifecycle.py`` at 40% — the idempotency
claims in the docstrings ("pass the existing publisher / heartbeat
to reuse them") were not pinned by tests. A regression there means
duplicate heartbeat threads, lost announces, or a config subscriber
that ignores the persisted-config path the plugin author asked for.

These tests mock ``DiscoveryPublisher`` + ``HeartbeatLoop`` so they
run without a broker — they're behavior tests for the wrapper logic,
not the publisher/loop implementations themselves.
"""
from __future__ import annotations

from pathlib import Path
from typing import Type
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.contract import CTF
from magellon_sdk.config_broker import ConfigSubscriber
from magellon_sdk.models import CTF_TASK, PluginInfo
from magellon_sdk.runner.lifecycle import (
    start_config_subscriber,
    start_discovery,
)


# ---------------------------------------------------------------------------
# Test plugin (minimal — discovery / config don't care about execute())
# ---------------------------------------------------------------------------

class _In(BaseModel):
    pass


class _Out(BaseModel):
    pass


class _Plugin(PluginBase[_In, _Out]):
    task_category = CTF_TASK

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="lifecycle-plugin", version="1.0.0", developer="test")

    @classmethod
    def input_schema(cls) -> Type[_In]:
        return _In

    @classmethod
    def output_schema(cls) -> Type[_Out]:
        return _Out

    def execute(self, input_data, *, reporter=None) -> _Out:
        return _Out()


# ---------------------------------------------------------------------------
# start_discovery — idempotency, announce semantics
# ---------------------------------------------------------------------------

def test_start_discovery_first_call_creates_publisher_and_heartbeat():
    """Cold start: no existing instances passed → both get created,
    heartbeat thread is started exactly once."""
    plugin = _Plugin()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher") as MockPub, \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop") as MockHB:
        publisher = MockPub.return_value
        heartbeat = MockHB.return_value

        pub_out, hb_out, announce = start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=15.0,
        )

        MockPub.assert_called_once()
        MockHB.assert_called_once()
        heartbeat.start.assert_called_once()
        publisher.announce.assert_called_once_with(CTF, announce)
        assert pub_out is publisher
        assert hb_out is heartbeat


def test_start_discovery_reuses_existing_publisher():
    """Warm reconnect: caller passes an existing publisher → no new
    one is constructed, but announce still fires (so a manager that
    booted after the plugin still picks the plugin up)."""
    plugin = _Plugin()
    existing_pub = MagicMock()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher") as MockPub, \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop"):
        pub_out, _hb, announce = start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=15.0,
            existing_publisher=existing_pub,
        )

        MockPub.assert_not_called()
        existing_pub.announce.assert_called_once_with(CTF, announce)
        assert pub_out is existing_pub


def test_start_discovery_reuses_existing_heartbeat_does_not_spawn_thread():
    """The dangerous regression: if the helper accidentally creates a
    NEW HeartbeatLoop when an existing one is passed, the plugin gets
    two heartbeat threads and the broker sees twice the traffic.
    Asserts on the construction count, not just the start count."""
    plugin = _Plugin()
    existing_hb = MagicMock()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher"), \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop") as MockHB:
        _pub, hb_out, _announce = start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=15.0,
            existing_heartbeat=existing_hb,
        )

        MockHB.assert_not_called()
        existing_hb.start.assert_not_called()  # already running; don't restart
        assert hb_out is existing_hb


def test_start_discovery_announce_failure_is_swallowed():
    """A broker hiccup at startup must not kill the plugin — the
    heartbeat will eventually carry the manager over. A regression
    that lets the AMQP exception propagate would mean the plugin's
    main.py fails on import in the field every time the broker is
    rebooting."""
    plugin = _Plugin()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher") as MockPub, \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop"):
        publisher = MockPub.return_value
        publisher.announce.side_effect = RuntimeError("broker rebooting")

        # Should not raise.
        pub_out, _hb, _ann = start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=15.0,
        )

        assert pub_out is publisher  # publisher returned despite announce failure


def test_start_discovery_announce_includes_plugin_manifest_and_task_queue():
    """The announce envelope is what the dispatcher reads to route to
    a specific backend (X.1's target_backend). Missing manifest or
    task_queue means the dispatcher can't match, and the plugin shows
    up as unreachable in the liveness registry."""
    plugin = _Plugin()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher") as MockPub, \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop"):
        _pub, _hb, announce = start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=15.0,
            task_queue="ctf_tasks_queue",
        )

        assert announce.plugin_id == "lifecycle-plugin"
        assert announce.plugin_version == "1.0.0"
        assert announce.task_queue == "ctf_tasks_queue"
        assert announce.category == "ctf"
        # Manifest is captured by value, not identity (plugin.manifest()
        # generates fresh UUIDs per call). Pin the structural fields the
        # dispatcher actually reads.
        assert announce.manifest.info.name == "lifecycle-plugin"
        assert announce.manifest.info.version == "1.0.0"
        assert announce.manifest.input_schema == plugin.manifest().input_schema


def test_start_discovery_heartbeat_uses_specified_interval():
    """Operator might tune heartbeat_interval_seconds for a slow
    network — the helper must thread it through to HeartbeatLoop's
    constructor, not silently use a default."""
    plugin = _Plugin()
    with patch("magellon_sdk.runner.lifecycle.DiscoveryPublisher"), \
         patch("magellon_sdk.runner.lifecycle.HeartbeatLoop") as MockHB:
        start_discovery(
            settings=MagicMock(),
            plugin=plugin,
            contract=CTF,
            heartbeat_interval_seconds=30.0,
        )

        kwargs = MockHB.call_args.kwargs
        assert kwargs["interval_seconds"] == 30.0


# ---------------------------------------------------------------------------
# start_config_subscriber — idempotency, persisted_path plumbing
# ---------------------------------------------------------------------------

def test_start_config_subscriber_creates_when_no_existing():
    sub = start_config_subscriber(
        settings=MagicMock(), contract=CTF, existing=None,
    )
    assert isinstance(sub, ConfigSubscriber)
    sub.stop()  # don't leak the subscription thread between tests


def test_start_config_subscriber_returns_existing_unchanged():
    """Reconnect path: the runner re-enters the lifecycle helper
    after a transient broker drop. Skipping the second start is what
    keeps a single subscription active — re-creating would leave the
    old one as a phantom subscriber on the broker."""
    existing = MagicMock(spec=ConfigSubscriber)
    sub = start_config_subscriber(
        settings=MagicMock(), contract=CTF, existing=existing,
    )
    assert sub is existing
    # No mutation: existing.start was NOT called by the helper.
    existing.start.assert_not_called()


def test_start_config_subscriber_threads_persisted_path_through(tmp_path):
    """A plugin author opting into persistent config tells the runner
    the path; the runner threads it through here. Regression check:
    the helper must not silently drop the kwarg (e.g. by forgetting
    to pass it to ``ConfigSubscriber.__init__``)."""
    persisted = tmp_path / "ctf.json"
    sub = start_config_subscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    try:
        # Internal attribute — pinned because there's no public getter
        # and changing the name would silently break this contract.
        assert sub._persisted_path == persisted
    finally:
        sub.stop()


def test_start_config_subscriber_persisted_path_ignored_when_reusing_existing(tmp_path):
    """If the caller passes both an existing subscriber AND a new
    persisted_path, the existing one's configuration wins. Otherwise
    we'd silently mutate the existing subscriber's behavior on
    reconnect — a footgun that's hard to debug.

    This pins the documented "warm reconnect: reuse existing as-is"
    semantics."""
    existing = ConfigSubscriber(
        settings=MagicMock(),
        contract=CTF,
        persisted_path=tmp_path / "original.json",
    )
    try:
        new_path = tmp_path / "ignored.json"
        sub = start_config_subscriber(
            settings=MagicMock(),
            contract=CTF,
            existing=existing,
            persisted_path=new_path,
        )
        # The original path is preserved; the new_path argument is ignored.
        assert sub is existing
        assert sub._persisted_path == tmp_path / "original.json"
    finally:
        existing.stop()

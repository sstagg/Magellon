"""Lifecycle helpers for :class:`PluginBrokerRunner`.

Extracted from ``runner.py`` in MB0 to make the composition visible
before the MessageBus lands. These wrappers own the construction and
start/announce calls for discovery + heartbeat and for the config
subscriber. The runner holds the returned references and drives
start/stop.

When the bus arrives (MB5) the implementations here collapse into
``magellon_sdk/bus/services/`` and call ``bus.events.publish`` /
``bus.events.subscribe`` instead of ``DiscoveryPublisher`` and
``ConfigSubscriber`` directly. The function signatures here are the
seam the bus migration will slot under.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.config_broker import ConfigSubscriber
from magellon_sdk.discovery import Announce, DiscoveryPublisher, HeartbeatLoop

logger = logging.getLogger(__name__)


def start_discovery(
    *,
    settings: Any,
    plugin: PluginBase,
    contract: CategoryContract,
    heartbeat_interval_seconds: float,
    task_queue: Optional[str] = None,
    existing_publisher: Optional[DiscoveryPublisher] = None,
    existing_heartbeat: Optional[HeartbeatLoop] = None,
) -> Tuple[DiscoveryPublisher, HeartbeatLoop, Announce]:
    """Announce the plugin and start the heartbeat loop.

    Idempotent across reconnects: pass the existing publisher /
    heartbeat to reuse them. First call creates both; later calls
    re-announce (so a manager that booted after the plugin still picks
    it up) but leave the heartbeat thread alone.

    ``task_queue`` is the runner's ``in_queue`` — piped into the
    :class:`Announce` so a dispatcher can route to this specific
    implementation's queue when multiple impls coexist.

    A broker hiccup at announce time is logged and swallowed — the
    heartbeat will eventually carry the manager over.
    """
    publisher = existing_publisher or DiscoveryPublisher(settings)
    info = plugin.get_info()
    manifest = plugin.manifest()
    announce = Announce(
        plugin_id=info.name,
        plugin_version=info.version,
        category=contract.category.name.lower(),
        manifest=manifest,
        task_queue=task_queue,
        backend_id=manifest.resolved_backend_id(),
    )
    try:
        publisher.announce(contract, announce)
    except Exception as exc:
        logger.warning("start_discovery: announce failed: %s", exc)

    heartbeat = existing_heartbeat
    if heartbeat is None:
        heartbeat = HeartbeatLoop(
            publisher=publisher,
            contract=contract,
            plugin_id=info.name,
            plugin_version=info.version,
            instance_id=announce.instance_id,
            interval_seconds=heartbeat_interval_seconds,
        )
        heartbeat.start()
    return publisher, heartbeat, announce


def start_config_subscriber(
    *,
    settings: Any,
    contract: CategoryContract,
    existing: Optional[ConfigSubscriber] = None,
) -> ConfigSubscriber:
    """Start a :class:`ConfigSubscriber` once per process.

    Idempotent: pass ``existing`` to skip the second start call on
    reconnect. The subscriber buffers updates on its own daemon thread;
    the runner drains the buffer between deliveries via
    :meth:`ConfigSubscriber.take_pending`.
    """
    if existing is not None:
        return existing
    subscriber = ConfigSubscriber(settings, contract=contract)
    subscriber.start()
    return subscriber


__all__ = ["start_discovery", "start_config_subscriber"]

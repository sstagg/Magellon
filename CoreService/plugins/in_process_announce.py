"""Announce in-process plugins on the liveness bus at startup (U1.1).

Broker plugins publish an :class:`Announce` message to
``magellon.plugins.announce.<category>.<plugin_id>`` on boot so
CoreService's liveness registry knows they exist. In-process plugins
(discovered by the filesystem walk in :mod:`plugins.registry`) have
historically NOT done this — which is why they appeared only in the
static registry, not in the unified plugins page.

This module closes the gap: at CoreService startup, after the bus is
installed, iterate the static registry and publish one Announce per
plugin. The liveness registry then contains both in-process AND broker
plugins with uniform shape.

The announce is best-effort (same contract broker plugins follow).
Failures are logged; they don't abort startup. A heartbeat loop is
**not** started here — in-process plugins share the CoreService
process lifetime, so "is the plugin alive" == "is CoreService alive."
The liveness registry's staleness threshold (60s) is longer than the
heartbeat interval (15s), so periodic announce-as-heartbeat keeps the
entry fresh.

Category lookup uses ``CATEGORIES`` from ``magellon_sdk.categories.contract``
keyed by the plugin's ``task_category.code``. Plugins that expose
``PARTICLE_PICKER`` / ``CTF`` / ``MOTIONCOR_CATEGORY`` / ``FFT`` all
route correctly without this module having to know about specific
categories.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional
from uuid import uuid4

from magellon_sdk.categories.contract import CATEGORIES
from magellon_sdk.discovery import Announce, DiscoveryPublisher, Heartbeat

from plugins.base import PluginBase
from plugins.registry import PluginEntry, registry

logger = logging.getLogger(__name__)

# One instance-id per plugin per CoreService process. Held for the
# lifetime of the process so heartbeat + announce share identity.
_INSTANCE_IDS: dict[str, str] = {}

_HEARTBEAT_INTERVAL_SECONDS = 15.0


def _resolve_contract(entry: PluginEntry):
    """Find the :class:`CategoryContract` for a discovered plugin.

    Plugins expose ``task_category`` (a :class:`TaskCategory` with a
    numeric ``code``). The SDK keys :data:`CATEGORIES` by that code.
    Returns ``None`` when the plugin's category isn't registered
    (bridge plugins during migration may not be); caller skips those.
    """
    plugin: PluginBase = entry.instance
    category = getattr(plugin, "task_category", None)
    if category is None:
        return None
    return CATEGORIES.get(int(category.code))


def _build_announce(entry: PluginEntry, instance_id: str) -> Announce:
    manifest = entry.manifest
    return Announce(
        plugin_id=entry.plugin_id,
        plugin_version=manifest.info.version,
        category=entry.category,
        instance_id=instance_id,
        manifest=manifest,
    )


def _build_heartbeat(entry: PluginEntry, instance_id: str) -> Heartbeat:
    return Heartbeat(
        plugin_id=entry.plugin_id,
        plugin_version=entry.manifest.info.version,
        category=entry.category,
        instance_id=instance_id,
        status="ready",
    )


def announce_in_process_plugins(rmq_settings) -> int:
    """Publish one :class:`Announce` per discovered in-process plugin.

    Called from CoreService startup after :func:`install_core_bus`.
    Returns the count of successful announces — callers can log it
    for visibility. Broken plugins are skipped, logged, and don't
    abort startup.
    """
    if not registry.list():
        logger.info("announce_in_process_plugins: no plugins to announce")
        return 0

    publisher = DiscoveryPublisher(rmq_settings)
    announced = 0
    for entry in registry.list():
        contract = _resolve_contract(entry)
        if contract is None:
            logger.debug(
                "announce_in_process_plugins: skipping %s — no CategoryContract",
                entry.plugin_id,
            )
            continue

        instance_id = _INSTANCE_IDS.setdefault(entry.plugin_id, str(uuid4()))
        try:
            publisher.announce(contract, _build_announce(entry, instance_id))
            announced += 1
            logger.info(
                "announced in-process plugin %s on magellon.plugins.announce.%s.%s",
                entry.plugin_id, contract.category.name, entry.plugin_id,
            )
        except Exception:
            logger.exception(
                "announce_in_process_plugins: announce failed for %s",
                entry.plugin_id,
            )
    return announced


def _heartbeat_loop(rmq_settings) -> None:
    publisher = DiscoveryPublisher(rmq_settings)
    while True:
        time.sleep(_HEARTBEAT_INTERVAL_SECONDS)
        for entry in registry.list():
            contract = _resolve_contract(entry)
            if contract is None:
                continue
            instance_id = _INSTANCE_IDS.get(entry.plugin_id)
            if instance_id is None:
                # Missed announce on startup; fill in so heartbeats
                # still correlate to something.
                instance_id = _INSTANCE_IDS.setdefault(entry.plugin_id, str(uuid4()))
            try:
                publisher.heartbeat(contract, _build_heartbeat(entry, instance_id))
            except Exception:
                logger.debug(
                    "heartbeat publish failed for %s (non-fatal)",
                    entry.plugin_id,
                )


_heartbeat_thread: Optional[threading.Thread] = None


def start_in_process_heartbeat(rmq_settings) -> None:
    """Start the heartbeat daemon. Idempotent — calling twice is safe."""
    global _heartbeat_thread
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(rmq_settings,),
        name="in-process-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


__all__ = ["announce_in_process_plugins", "start_in_process_heartbeat"]

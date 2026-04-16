"""Plugin-side and CoreService-side bus factories.

Plugins run as their own Python processes — each needs its own
:class:`MessageBus` instance wired from its own settings. This module
provides one-liners so a plugin's ``main.py`` doesn't duplicate the
construction boilerplate.

Three flavors, matching the three binder implementations:

- :func:`build_rmq_bus` / :func:`install_rmq_bus` — production path,
  pika-backed. Use in plugin processes and CoreService startup.
- :func:`build_inmemory_bus` / :func:`install_inmemory_bus` — for
  tests and local dev that want broker-shaped behavior without RMQ.
- :func:`build_mock_bus` / :func:`install_mock_bus` — for unit tests
  that want synchronous dispatch (no threads).

``install_*`` variants additionally wire :func:`get_bus` so every
subsequent ``get_bus()`` call returns the installed bus. That's the
seam a plugin's ``main.py`` uses::

    from magellon_sdk.bus.bootstrap import install_rmq_bus
    from config import app_settings

    install_rmq_bus(app_settings.rabbitmq_settings)
    runner = PluginBrokerRunner(...)
    runner.start_blocking()
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from magellon_sdk.bus._facade import DefaultMessageBus, get_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.policy import AuditLogConfig


def build_rmq_bus(
    settings: Any,
    *,
    legacy_queue_map: Optional[Dict[str, str]] = None,
    audit: Optional[AuditLogConfig] = None,
) -> MessageBus:
    """Construct an :class:`RmqBinder`-backed bus and start it.

    ``settings`` is any object with the fields ``RabbitmqClient``
    expects (``HOST_NAME``, ``USER_NAME``, ``PASSWORD``, and optional
    ``PORT`` / ``VIRTUAL_HOST``).

    Raises on broker failure — callers that want lazy boot should
    pass this to :meth:`get_bus.set_factory` instead of calling
    :func:`install_rmq_bus`.
    """
    from magellon_sdk.bus.binders.rmq import RmqBinder

    binder = RmqBinder(
        settings=settings, legacy_queue_map=legacy_queue_map, audit=audit
    )
    bus = DefaultMessageBus(binder)
    bus.start()
    return bus


def install_rmq_bus(
    settings: Any,
    *,
    legacy_queue_map: Optional[Dict[str, str]] = None,
    audit: Optional[AuditLogConfig] = None,
) -> MessageBus:
    """Build an RMQ-backed bus and install as the process-wide bus.

    Convenience: one call at plugin or service startup and every
    subsequent ``get_bus()`` returns the installed bus.
    """
    bus = build_rmq_bus(
        settings, legacy_queue_map=legacy_queue_map, audit=audit
    )
    get_bus.override(bus)
    return bus


def build_inmemory_bus() -> MessageBus:
    """Construct an :class:`InMemoryBinder`-backed bus and start it.

    Broker-shaped, no RMQ. Use when tests want real consumer threading
    and ack/nack/DLQ routing but don't want to spin up a container.
    """
    from magellon_sdk.bus.binders.inmemory import InMemoryBinder

    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    return bus


def install_inmemory_bus() -> MessageBus:
    """Build an in-memory bus and install as the process-wide bus."""
    bus = build_inmemory_bus()
    get_bus.override(bus)
    return bus


def build_mock_bus() -> MessageBus:
    """Construct a :class:`MockBinder`-backed bus and start it.

    Synchronous dispatch, no threads. Prefer for unit tests that
    assert shape (published lists, handler invocation) over behavior.
    """
    from magellon_sdk.bus.binders.mock import MockBinder

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    return bus


def install_mock_bus() -> MessageBus:
    """Build a mock bus and install as the process-wide bus."""
    bus = build_mock_bus()
    get_bus.override(bus)
    return bus


__all__ = [
    "build_inmemory_bus",
    "build_mock_bus",
    "build_rmq_bus",
    "install_inmemory_bus",
    "install_mock_bus",
    "install_rmq_bus",
]

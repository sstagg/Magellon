"""Binder implementations.

- :class:`MockBinder` (``mock``): synchronous, in-memory; for unit tests
  that assert shape. Publishes dispatch immediately inside the call.
- :class:`InMemoryBinder` (``inmemory``): threaded, queue-backed,
  broker-shaped; for integration tests and local dev without RMQ.
  Honors ack / nack / DLQ via ``classify_exception``.
- :class:`RmqBinder` (``rmq``): production pika-backed.
"""
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.binders.mock import MockBinder

__all__ = ["InMemoryBinder", "MockBinder"]

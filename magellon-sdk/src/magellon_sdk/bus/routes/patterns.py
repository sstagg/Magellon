"""Subscription patterns — subject globs the binder translates to its
native wildcard syntax.

Convention (NATS-style, broker-neutral):

- ``*`` matches exactly one subject segment
- ``>`` matches one or more tail segments

RMQ binder translates ``>`` → ``#`` (which RMQ treats as zero-or-more,
a superset of ``>`` — the extra zero-segment match is harmless because
the subject always has at least the fixed prefix).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventPattern:
    """A subscription pattern for ``bus.events.subscribe``.

    Patterns are produced by ``*.all()`` / ``*.broadcast()`` class
    methods on the concrete route types — callers don't construct
    ``EventPattern`` directly.
    """

    subject_glob: str


__all__ = ["EventPattern"]

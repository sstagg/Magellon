"""Unit tests for :mod:`magellon_sdk.bus.services.cancel_registry` (G.1).

Pins the thin contract:

- ``CancelRegistry.mark_cancelled`` + ``is_cancelled`` round-trip on
  both ``UUID`` and ``str`` keys.
- ``start_cancel_listener`` registers exactly one bus subscription
  on ``CancelRoute.all()``.
- The registered handler decodes the envelope into ``CancelMessage``
  and marks the job_id in the registry.
- Malformed payloads raise ``PermanentError`` so the binder DLQs.

The end-to-end cancel flow (runner subscribes → BoundStepReporter
raises → result envelope has cancelled=True) is covered by
``CoreService/tests/test_plugin_broker_runner_cancel.py``.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from magellon_sdk.bus.routes.event_route import CancelRoute
from magellon_sdk.bus.services.cancel_registry import (
    CancelMessage,
    CancelRegistry,
    start_cancel_listener,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError


def test_registry_marks_and_reads_by_uuid_or_str():
    reg = CancelRegistry()
    jid = uuid4()

    reg.mark_cancelled(jid)

    # UUID + str should both hit.
    assert reg.is_cancelled(jid) is True
    assert reg.is_cancelled(str(jid)) is True

    # Unrelated job: not cancelled.
    assert reg.is_cancelled(uuid4()) is False

    # None returns False — protects reporter code paths when the
    # reporter was built without a bound job_id.
    assert reg.is_cancelled(None) is False


def test_registry_clear_drops_entry():
    reg = CancelRegistry()
    jid = uuid4()
    reg.mark_cancelled(jid)
    reg.clear(jid)
    assert reg.is_cancelled(jid) is False


def test_registry_reset_clears_all():
    reg = CancelRegistry()
    a, b = uuid4(), uuid4()
    reg.mark_cancelled(a)
    reg.mark_cancelled(b)
    reg.reset()
    assert reg.snapshot() == set()


def test_start_cancel_listener_subscribes_and_handler_marks_registry():
    reg = CancelRegistry()
    bus = MagicMock()
    handle = MagicMock()
    bus.events.subscribe.return_value = handle

    listener = start_cancel_listener(registry=reg, bus=bus)

    # Registered exactly one subscription on CancelRoute.all().
    assert bus.events.subscribe.call_count == 1
    pattern, handler = bus.events.subscribe.call_args.args
    assert pattern.subject_glob == CancelRoute.all().subject_glob

    # Invoking the registered handler with a valid cancel envelope
    # marks the job_id.
    jid = uuid4()
    msg = CancelMessage(job_id=jid, reason="operator")
    envelope = Envelope.wrap(
        source="test",
        type="magellon.plugin.cancel.v1",
        subject=CancelRoute.for_job(str(jid)).subject,
        data=msg,
    )
    handler(envelope)

    assert reg.is_cancelled(jid) is True

    # stop() closes the handle (shutdown path).
    listener.stop()
    handle.close.assert_called_once()


def test_handler_raises_permanent_error_on_bad_payload():
    """Malformed payload → DLQ. Redelivering won't help: the next
    delivery has the same bad shape. PermanentError is how the
    classifier gets routed to DLQ."""
    reg = CancelRegistry()
    bus = MagicMock()
    start_cancel_listener(registry=reg, bus=bus)

    _, handler = bus.events.subscribe.call_args.args

    bad_envelope = Envelope.wrap(
        source="test",
        type="x",
        subject="magellon.plugins.cancel.bogus",
        data={"job_id": "not-a-uuid"},
    )

    with pytest.raises(PermanentError, match="bad CancelMessage payload"):
        handler(bad_envelope)

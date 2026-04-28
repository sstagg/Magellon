"""Unit tests for ``CoreService/scripts/migrate_dlq_topology.py``.

The migration script is the single highest-risk operation in the bus
plan: ``queue_delete`` discards every in-flight message, so a regression
that flips the wrong flag or skips a precondition is silent until it
hits production. Audit (gap #1) flagged this script as having zero
tests; this file covers the critical contracts.

We mock ``_open_connection`` to return a fake pika connection so tests
run without a live broker. The script's pika imports happen at module
load (so we still need pika installed), but no real AMQP traffic flows.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Import the script as a module without making scripts/ a package.
# ---------------------------------------------------------------------------

_SCRIPT_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts",
        "migrate_dlq_topology.py",
    )
)
_MODULE_NAME = "migrate_dlq_topology_under_test"


@pytest.fixture(scope="module")
def mig():
    """Load the script as a module once per test module.

    We register the module in ``sys.modules`` before ``exec_module``
    because the script defines ``@dataclass`` types whose
    ``__module__`` attribute gets resolved via ``sys.modules`` during
    field-type resolution. Without the registration, dataclasses
    raises an ``AttributeError`` on ``None.__dict__``.
    """
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(_MODULE_NAME, None)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _frame(*, message_count: int = 0, consumer_count: int = 0) -> MagicMock:
    """Build a fake passive-declare response."""
    frame = MagicMock()
    frame.method.message_count = message_count
    frame.method.consumer_count = consumer_count
    return frame


def _mock_conn(*, frame: MagicMock | None = None) -> tuple[MagicMock, list[MagicMock]]:
    """Build a fake pika connection that hands out fresh channel mocks.

    Returns (connection, channels-list) so tests can inspect every
    channel that was used. The script opens fresh channels per
    operation; tests that count calls need to know which channel
    they happened on.
    """
    conn = MagicMock()
    channels: list[MagicMock] = []
    response = frame if frame is not None else _frame()

    def _make_channel():
        ch = MagicMock()
        ch.is_open = True
        ch.queue_declare.return_value = response
        channels.append(ch)
        return ch

    conn.channel.side_effect = _make_channel
    return conn, channels


# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

def test_unknown_queue_name_exits(mig, monkeypatch):
    """``--queue X`` where X is not in the production catalog must
    fail loudly rather than silently no-op. Operator typoed the name;
    we should not pretend the queue exists."""
    monkeypatch.setattr(mig, "_open_connection", lambda url: MagicMock())
    with pytest.raises(SystemExit) as exc:
        mig.main(["--queue", "no_such_queue", "--dry-run"])
    assert "Unknown queue" in str(exc.value)


def test_no_action_specified_exits(mig, monkeypatch):
    """Calling with no --queue / --all / --verify must not silently
    run a no-op — the operator probably meant to specify."""
    monkeypatch.setattr(mig, "_open_connection", lambda url: MagicMock())
    with pytest.raises(SystemExit) as exc:
        mig.main(["--dry-run"])
    assert "Specify one of" in str(exc.value)


def test_all_in_live_mode_requires_yes(mig, monkeypatch):
    """``--all`` with destructive intent must require explicit --yes
    so a stray invocation in shell history can't drop production
    queues. Returns exit code 2 to distinguish from a runtime
    failure (1)."""
    monkeypatch.setattr(mig, "_open_connection", lambda url: MagicMock())
    rc = mig.main(["--all"])  # no --yes, no --dry-run, no --verify
    assert rc == 2


def test_all_dry_run_does_not_require_yes(mig, monkeypatch):
    """Dry-run is read-only by definition — the safety check exists
    to guard destructive ops, not to gate inspection."""
    conn, _channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    rc = mig.main(["--all", "--dry-run"])
    assert rc == 0


def test_verify_does_not_require_yes(mig, monkeypatch):
    """Same logic — --verify is read-only."""
    conn, _channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    rc = mig.main(["--verify"])
    assert rc == 0


# ---------------------------------------------------------------------------
# Dry-run guarantees no destructive ops
# ---------------------------------------------------------------------------

def test_dry_run_calls_no_queue_delete(mig, monkeypatch):
    """Dry-run on every queue must never call queue_delete on any
    channel. This is THE invariant — operator runs --dry-run against
    production to verify safety; if delete leaks through, that's
    catastrophic."""
    conn, channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    rc = mig.main(["--all", "--dry-run"])
    assert rc == 0
    for ch in channels:
        ch.queue_delete.assert_not_called()


def test_dry_run_calls_no_queue_bind(mig, monkeypatch):
    """Same invariant for queue_bind — dry-run must not touch
    exchange bindings either."""
    conn, channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    mig.main(["--all", "--dry-run"])
    for ch in channels:
        ch.queue_bind.assert_not_called()


def test_dry_run_only_calls_passive_declare(mig, monkeypatch):
    """The only queue_declare allowed during dry-run is passive=True
    (read-only inspection). Non-passive declare with arguments would
    create the DLQ queue, which is destructive."""
    conn, channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    mig.main(["--all", "--dry-run"])

    for ch in channels:
        for call in ch.queue_declare.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("passive") is True, (
                f"non-passive declare during dry-run: {call}"
            )


# ---------------------------------------------------------------------------
# --queue X targets only X
# ---------------------------------------------------------------------------

def test_single_queue_only_inspects_that_queue(mig, monkeypatch):
    """``--queue ctf_tasks_queue --dry-run`` must NOT touch
    motioncor_tasks_queue or any other queue. A regression here would
    mean the migration accidentally cascades to queues the operator
    didn't authorize."""
    conn, channels = _mock_conn()
    monkeypatch.setattr(mig, "_open_connection", lambda url: conn)
    mig.main(["--queue", "ctf_tasks_queue", "--dry-run"])

    other_queue_names = {
        "motioncor_tasks_queue", "fft_tasks_queue",
        "ctf_out_tasks_queue", "motioncor_out_tasks_queue",
        "fft_out_tasks_queue", "core_step_events_queue",
    }
    touched_queues: set[str] = set()
    for ch in channels:
        for call in ch.queue_declare.call_args_list:
            q = call.kwargs.get("queue") or (call.args[0] if call.args else None)
            if q:
                touched_queues.add(q)
        for call in ch.queue_delete.call_args_list:
            q = call.kwargs.get("queue") or (call.args[0] if call.args else None)
            if q:
                touched_queues.add(q)

    assert touched_queues & other_queue_names == set(), (
        f"unauthorized queues touched: {touched_queues & other_queue_names}"
    )
    assert "ctf_tasks_queue" in touched_queues


# ---------------------------------------------------------------------------
# Drain preconditions — the if_empty / if_unused safety net
# ---------------------------------------------------------------------------

def test_drain_refuses_when_consumer_present(mig):
    """If anyone is still consuming the queue at migration time,
    queue_delete with if_unused=True would fail anyway. Catch it
    earlier so the operator gets a clean error message."""
    ch = MagicMock()
    ch.queue_declare.return_value = _frame(consumer_count=1)
    ok = mig._drain_and_verify(ch, "q", dry_run=False)
    assert ok is False


def test_drain_refuses_when_messages_pending(mig):
    """if_empty=True on queue_delete would raise if messages remain;
    we'd rather fail with our own message than let pika's exception
    confuse the operator."""
    ch = MagicMock()
    ch.queue_declare.return_value = _frame(message_count=5)
    ok = mig._drain_and_verify(ch, "q", dry_run=False)
    assert ok is False


def test_drain_returns_false_when_queue_missing(mig):
    """Passive declare on a non-existent queue raises
    ChannelClosedByBroker. The script catches it and returns False
    (skip), not True (proceed) — there's nothing to migrate."""
    import pika.exceptions as pex
    ch = MagicMock()
    ch.queue_declare.side_effect = pex.ChannelClosedByBroker(404, "not found")
    ok = mig._drain_and_verify(ch, "nope", dry_run=False)
    assert ok is False


def test_drain_passes_when_empty_and_unused(mig):
    """The happy path — queue exists, drained, no consumers — must
    return True so the script proceeds to the redeclare step."""
    ch = MagicMock()
    ch.queue_declare.return_value = _frame(message_count=0, consumer_count=0)
    ok = mig._drain_and_verify(ch, "q", dry_run=False)
    assert ok is True


# ---------------------------------------------------------------------------
# Live redeclare — the operation order matters
# ---------------------------------------------------------------------------

def test_redeclare_calls_in_correct_order(mig):
    """Order matters: delete first (releases the name), then declare
    DLQ (so the dead-letter target exists when the main queue starts
    routing to it), then declare main with DLQ args. Reversing
    declare-DLQ + declare-main means the first DLQ-bound message
    can hit a non-existent target."""
    ch = MagicMock()
    spec = mig._QueueSpec("ctf_tasks_queue")

    mig._redeclare_with_dlq(ch, spec, dry_run=False)

    call_seq = [c[0] for c in ch.method_calls]
    assert call_seq == ["queue_delete", "queue_declare", "queue_declare"]


def test_redeclare_passes_dlq_args_on_main_queue(mig):
    """The main queue must be redeclared with x-dead-letter-exchange
    and x-dead-letter-routing-key matching the DLQ name. If these
    args are missing or wrong the broker won't dead-letter at all."""
    ch = MagicMock()
    spec = mig._QueueSpec("ctf_tasks_queue")

    mig._redeclare_with_dlq(ch, spec, dry_run=False)

    # Second queue_declare call is the main queue; first is the DLQ.
    declare_calls = [c for c in ch.method_calls if c[0] == "queue_declare"]
    assert len(declare_calls) == 2
    main_kwargs = declare_calls[1].kwargs
    assert main_kwargs["arguments"] == {
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "ctf_tasks_queue_dlq",
    }
    assert main_kwargs["durable"] is True


def test_redeclare_dlq_is_durable_no_dlq_of_its_own(mig):
    """The DLQ itself must be durable (so ops doesn't lose poison
    messages on broker restart) but does NOT get DLQ args of its
    own — that would be a recursive dead-letter chain."""
    ch = MagicMock()
    spec = mig._QueueSpec("ctf_tasks_queue")

    mig._redeclare_with_dlq(ch, spec, dry_run=False)

    declare_calls = [c for c in ch.method_calls if c[0] == "queue_declare"]
    dlq_kwargs = declare_calls[0].kwargs
    assert dlq_kwargs["queue"] == "ctf_tasks_queue_dlq"
    assert dlq_kwargs["durable"] is True
    # No DLQ-args on the DLQ itself — would create a recursion.
    assert "arguments" not in dlq_kwargs


def test_redeclare_reapplies_topic_bindings(mig):
    """``core_step_events_queue`` was bound to the
    ``magellon.events`` topic exchange with routing key
    ``job.*.step.*``. Delete-and-redeclare drops bindings; the
    rebind step is what restores them. Skipping this means step
    events stop reaching CoreService and the UI goes silent."""
    ch = MagicMock()
    spec = mig._QueueSpec(
        "core_step_events_queue",
        exchange="magellon.events",
        routing_keys=("job.*.step.*",),
    )

    mig._redeclare_with_dlq(ch, spec, dry_run=False)

    binds = [c for c in ch.method_calls if c[0] == "queue_bind"]
    assert len(binds) == 1
    assert binds[0].kwargs == {
        "queue": "core_step_events_queue",
        "exchange": "magellon.events",
        "routing_key": "job.*.step.*",
    }


def test_redeclare_does_not_bind_when_no_routing_keys(mig):
    """Default-exchange queues (the task / out queues) have no
    bindings; queue_bind must not be called for them."""
    ch = MagicMock()
    spec = mig._QueueSpec("ctf_tasks_queue")  # no exchange / routing_keys

    mig._redeclare_with_dlq(ch, spec, dry_run=False)

    binds = [c for c in ch.method_calls if c[0] == "queue_bind"]
    assert binds == []


# ---------------------------------------------------------------------------
# DLQ args helper — keep the contract pinned
# ---------------------------------------------------------------------------

def test_dlq_args_match_sdk_helper(mig):
    """The script and ``RabbitmqClient.declare_queue_with_dlq`` must
    produce identical ``x-*`` args — otherwise a queue migrated by
    the script and a queue declared by a fresh SDK at boot would
    have *different* DLQ topology, leading to silent breakage on
    redeploy.

    We don't import the SDK helper here (would require the SDK
    package layout); instead we pin the literal shape the script
    produces. If the SDK changes, the failing test forces the
    operator to update both sides together.
    """
    args = mig._dlq_args("ctf_tasks_queue")
    assert args == {
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "ctf_tasks_queue_dlq",
    }


def test_dlq_args_use_per_queue_routing_key(mig):
    """The DLQ name is per-queue (suffix ``_dlq``) so DLQs don't
    collide. Wrong: a single shared DLQ for everything — operators
    can't tell which plugin produced the poison."""
    ctf = mig._dlq_args("ctf_tasks_queue")
    mc = mig._dlq_args("motioncor_tasks_queue")
    assert ctf["x-dead-letter-routing-key"] != mc["x-dead-letter-routing-key"]

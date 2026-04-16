"""RmqBinder unit tests (MB2).

Mocks pika at the call boundary so these run in CI without a broker.
Integration tests against a live RMQ container are gated on
``@pytest.mark.integration`` and live alongside the RMQ transport
integration tests.

Coverage:
- start() declares both event exchanges
- publish_task calls basic_publish on default exchange with the
  resolved (possibly-legacy) queue name as routing_key
- publish_event picks magellon.plugins vs magellon.events by subject
- subscribe_events binds a queue to the exchange with the translated
  RMQ routing key (``>`` → ``#``)
- legacy_queue_map translates bus subject to today's queue name
- audit hook writes a JSON line when enabled for that subject
- redelivery counter: reads pika header, falls back to boolean
- handler exception → classify_exception → ack/nack/requeue routing
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.bus import AuditLogConfig, TaskConsumerPolicy
from magellon_sdk.bus.binders.rmq import (
    EXCHANGE_EVENTS,
    EXCHANGE_PLUGINS,
    RmqBinder,
    exchange_for_pattern,
    exchange_for_subject,
    glob_to_rmq_routing_key,
)
from magellon_sdk.bus.binders.rmq.audit import write_audit_entry
from magellon_sdk.bus.routes import (
    ConfigRoute,
    HeartbeatRoute,
    StepEventRoute,
    TaskResultRoute,
    TaskRoute,
)
from magellon_sdk.categories.contract import CTF
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError, RetryableError


# ---------------------------------------------------------------------------
# Topology helpers (pure functions, no mocking needed)
# ---------------------------------------------------------------------------

class TestTopology:

    def test_exchange_for_subject_picks_plugins_for_magellon_plugins(self):
        assert exchange_for_subject("magellon.plugins.heartbeat.ctf.x") == EXCHANGE_PLUGINS
        assert exchange_for_subject("magellon.plugins.config.broadcast") == EXCHANGE_PLUGINS

    def test_exchange_for_subject_picks_events_for_step_events(self):
        assert exchange_for_subject("job.42.step.ctf") == EXCHANGE_EVENTS

    def test_exchange_for_pattern_applies_the_same_rule(self):
        assert exchange_for_pattern("magellon.plugins.heartbeat.>") == EXCHANGE_PLUGINS
        assert exchange_for_pattern("job.*.step.*") == EXCHANGE_EVENTS

    def test_glob_to_rmq_translates_tail_wildcard(self):
        assert glob_to_rmq_routing_key("magellon.plugins.heartbeat.>") == "magellon.plugins.heartbeat.#"
        # single-segment * is unchanged — both syntaxes agree
        assert glob_to_rmq_routing_key("job.*.step.*") == "job.*.step.*"


# ---------------------------------------------------------------------------
# Audit writer (filesystem, no pika)
# ---------------------------------------------------------------------------

class TestAuditWriter:

    def test_writes_json_line_when_enabled_and_route_matches(self, tmp_path: Path):
        subject = "magellon.tasks.ctf"
        cfg = AuditLogConfig(
            enabled=True, root=str(tmp_path), routes=(subject,)
        )
        env = _env({"img": "x.mrc"})

        write_audit_entry(cfg, subject, env)

        path = tmp_path / subject / "messages.json"
        assert path.exists()
        content = path.read_text()
        assert content.endswith("\n")
        # One line, valid JSON
        lines = content.strip().splitlines()
        assert len(lines) == 1

    def test_skips_when_route_not_in_scope(self, tmp_path: Path):
        cfg = AuditLogConfig(
            enabled=True, root=str(tmp_path), routes=("magellon.tasks.ctf",)
        )
        write_audit_entry(cfg, "magellon.tasks.motioncor", _env({}))
        assert not (tmp_path / "magellon.tasks.motioncor").exists()

    def test_skips_when_disabled(self, tmp_path: Path):
        cfg = AuditLogConfig(enabled=False, root=str(tmp_path), routes=("x",))
        write_audit_entry(cfg, "x", _env({}))
        assert not (tmp_path / "x").exists()

    def test_failures_are_swallowed(self, tmp_path: Path):
        """A broken audit path must never break a dispatch."""
        # Point root at an existing file — makedirs will raise.
        blocker = tmp_path / "blocker"
        blocker.write_text("")
        cfg = AuditLogConfig(
            enabled=True,
            root=str(blocker),  # not a directory
            routes=("magellon.tasks.ctf",),
        )
        # Must not raise.
        write_audit_entry(cfg, "magellon.tasks.ctf", _env({}))

    def test_appends_rather_than_overwrites(self, tmp_path: Path):
        cfg = AuditLogConfig(
            enabled=True, root=str(tmp_path), routes=("magellon.tasks.ctf",)
        )
        write_audit_entry(cfg, "magellon.tasks.ctf", _env({"n": 1}))
        write_audit_entry(cfg, "magellon.tasks.ctf", _env({"n": 2}))

        path = tmp_path / "magellon.tasks.ctf" / "messages.json"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# Binder with mocked RabbitmqClient
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Patch RabbitmqClient so no pika connection is ever opened."""
    with patch(
        "magellon_sdk.bus.binders.rmq.binder.RabbitmqClient", autospec=True
    ) as cls:
        # Every RabbitmqClient(...) constructor call yields a mock instance.
        # Return value is the class; instances come from cls.return_value
        # but we need a fresh mock per construction so tests can inspect
        # independently. side_effect giving a new MagicMock each call:
        def _new(*args, **kwargs):
            inst = MagicMock()
            inst.connection = MagicMock()
            inst.connection.is_closed = False
            inst.channel = MagicMock()
            return inst

        cls.side_effect = _new
        yield cls


@pytest.fixture
def binder(mock_client):
    b = RmqBinder(settings=MagicMock())
    b.start()
    yield b
    b.close()


# -- lifecycle ------------------------------------------------------------

def test_start_declares_both_event_exchanges(binder):
    """start() must declare the two topic exchanges the binder uses."""
    channel = binder._client.channel  # type: ignore[union-attr]
    declared = [c.kwargs.get("exchange") or c.args[0] for c in channel.exchange_declare.call_args_list]
    assert EXCHANGE_PLUGINS in declared
    assert EXCHANGE_EVENTS in declared


def test_start_is_idempotent(mock_client):
    b = RmqBinder(settings=MagicMock())
    b.start()
    b.start()
    # Only one RabbitmqClient construction
    assert mock_client.call_count == 1
    b.close()


def test_require_started_raises_when_not_started():
    b = RmqBinder(settings=MagicMock())
    with pytest.raises(RuntimeError, match="not started"):
        b.publish_task(TaskRoute.for_category(CTF), _env({}))


# -- publish_task ---------------------------------------------------------

def test_publish_task_uses_default_exchange_and_subject_as_routing_key(binder):
    route = TaskRoute.for_category(CTF)  # subject: magellon.tasks.ctf

    receipt = binder.publish_task(route, _env({"img": "x.mrc"}))

    assert receipt.ok
    binder._client.publish_message.assert_called_once()
    body, queue = binder._client.publish_message.call_args[0]
    assert queue == "magellon.tasks.ctf"
    assert b'"img":"x.mrc"' in body  # envelope JSON contains the data


def test_publish_task_uses_legacy_queue_map_when_provided(mock_client):
    """With a map, subject magellon.tasks.ctf → ctf_tasks_queue on wire."""
    legacy = {"magellon.tasks.ctf": "ctf_tasks_queue"}
    b = RmqBinder(settings=MagicMock(), legacy_queue_map=legacy)
    b.start()

    b.publish_task(TaskRoute.for_category(CTF), _env({"x": 1}))

    _, queue = b._client.publish_message.call_args[0]
    assert queue == "ctf_tasks_queue"
    b.close()


def test_publish_task_returns_ok_false_on_broker_error(binder):
    from pika.exceptions import AMQPConnectionError
    binder._client.publish_message.side_effect = AMQPConnectionError("down")

    receipt = binder.publish_task(TaskRoute.for_category(CTF), _env({}))

    assert receipt.ok is False
    assert receipt.error and "down" in receipt.error


def test_publish_task_writes_audit_when_subject_is_in_scope(tmp_path, mock_client):
    route = TaskRoute.for_category(CTF)
    b = RmqBinder(
        settings=MagicMock(),
        audit=AuditLogConfig(
            enabled=True, root=str(tmp_path), routes=(route.subject,)
        ),
    )
    b.start()
    b.publish_task(route, _env({"img": "x.mrc"}))
    assert (tmp_path / route.subject / "messages.json").exists()
    b.close()


def test_publish_task_no_audit_when_route_not_in_scope(tmp_path, mock_client):
    """Selective audit: CTF in scope, MotionCor not."""
    b = RmqBinder(
        settings=MagicMock(),
        audit=AuditLogConfig(
            enabled=True,
            root=str(tmp_path),
            routes=("magellon.tasks.ctf",),
        ),
    )
    b.start()
    b.publish_task(TaskRoute.for_category(CTF), _env({}))
    b.publish_task(TaskRoute.named("magellon.tasks.motioncor"), _env({}))

    assert (tmp_path / "magellon.tasks.ctf" / "messages.json").exists()
    assert not (tmp_path / "magellon.tasks.motioncor").exists()
    b.close()


# -- consume_tasks: ack / nack / DLQ routing via classify_exception -------

def _invoke_consumer_callback(binder, route, policy, handler):
    """Register a consumer and return the pika callback (the fn passed
    to client.consume), plus a factory for (ch, method, properties)
    tuples so tests can drive the callback manually."""
    client = None
    # Capture the created consumer client so we can grab the callback.
    # binder.consume_tasks constructs a new RabbitmqClient; the mock
    # fixture returns a fresh MagicMock each time.
    binder.consume_tasks(route, handler, policy)
    # The LAST client RabbitmqClient instance (from mock_client.side_effect)
    # is the consumer client. Pull it from its .consume call args.
    handle = binder._consumer_handles[-1]
    client = handle._client
    callback = client.consume.call_args[0][1]
    return callback, client


def test_consume_calls_qos_only_when_prefetch_set(binder):
    received = []
    policy_none = TaskConsumerPolicy()  # prefetch=None
    policy_one = TaskConsumerPolicy(prefetch=1)

    binder.consume_tasks(TaskRoute.for_category(CTF), received.append, policy_none)
    client_a = binder._consumer_handles[-1]._client
    client_a.channel.basic_qos.assert_not_called()

    binder.consume_tasks(TaskRoute.for_category(CTF), received.append, policy_one)
    client_b = binder._consumer_handles[-1]._client
    client_b.channel.basic_qos.assert_called_once_with(prefetch_count=1)


def test_consume_callback_acks_on_success(binder):
    received = []
    callback, _ = _invoke_consumer_callback(
        binder, TaskRoute.for_category(CTF), TaskConsumerPolicy(), received.append
    )
    ch, method, props = _ch_method_props()
    body = _env({"img": "x.mrc"}).model_dump_json().encode()

    callback(ch, method, props, body)

    assert len(received) == 1
    ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)
    ch.basic_nack.assert_not_called()


def test_consume_callback_requeues_retryable_error(binder):
    def handler(env):
        raise RetryableError("nfs blip")

    callback, _ = _invoke_consumer_callback(
        binder, TaskRoute.for_category(CTF), TaskConsumerPolicy(), handler
    )
    ch, method, props = _ch_method_props()
    callback(ch, method, props, _env({}).model_dump_json().encode())

    ch.basic_nack.assert_called_once_with(delivery_tag=method.delivery_tag, requeue=True)


def test_consume_callback_dlqs_permanent_error(binder):
    def handler(env):
        raise PermanentError("bad input")

    callback, _ = _invoke_consumer_callback(
        binder, TaskRoute.for_category(CTF), TaskConsumerPolicy(), handler
    )
    ch, method, props = _ch_method_props()
    callback(ch, method, props, _env({}).model_dump_json().encode())

    ch.basic_nack.assert_called_once_with(delivery_tag=method.delivery_tag, requeue=False)


def test_consume_callback_reads_magellon_redelivery_header(binder):
    """When the x-magellon-redelivery header is set, it's the source
    of truth for the classifier. Boolean method.redelivered is the
    fallback."""
    captured = []

    def handler(env):
        raise RetryableError("blip")

    callback, _ = _invoke_consumer_callback(
        binder, TaskRoute.for_category(CTF), TaskConsumerPolicy(), handler
    )

    # With header=5, classify_exception sees 5
    ch, method, props = _ch_method_props(headers={"x-magellon-redelivery": 5})
    callback(ch, method, props, _env({}).model_dump_json().encode())
    # Behavior still requeues (RetryableError) — but count comes from header
    ch.basic_nack.assert_called_once()


# -- purge_tasks ----------------------------------------------------------

def test_purge_tasks_returns_message_count_and_purges(binder):
    route = TaskRoute.for_category(CTF)
    # Set up channel.queue_declare to return a frame with message_count=7
    frame = MagicMock()
    frame.method.message_count = 7
    binder._client.channel.queue_declare.return_value = frame

    count = binder.purge_tasks(route)

    assert count == 7
    binder._client.channel.queue_declare.assert_called_with(
        queue="magellon.tasks.ctf", passive=True
    )
    binder._client.channel.queue_purge.assert_called_with(queue="magellon.tasks.ctf")


# -- publish_event --------------------------------------------------------

def test_publish_event_routes_to_plugins_exchange_for_heartbeat(binder):
    route = HeartbeatRoute.for_plugin(CTF, "ctffind4")

    binder.publish_event(route, _env({"status": "ready"}))

    call = binder._client.channel.basic_publish.call_args
    assert call.kwargs["exchange"] == EXCHANGE_PLUGINS
    assert call.kwargs["routing_key"] == route.subject


def test_publish_event_routes_to_events_exchange_for_step_events(binder):
    route = StepEventRoute.create(job_id="abc", step="ctf")

    binder.publish_event(route, _env({"pct": 50}))

    call = binder._client.channel.basic_publish.call_args
    assert call.kwargs["exchange"] == EXCHANGE_EVENTS
    assert call.kwargs["routing_key"] == "job.abc.step.ctf"


def test_publish_event_routes_config_broadcast_on_plugins_exchange(binder):
    binder.publish_event(ConfigRoute.broadcast(), _env({"debug": True}))
    call = binder._client.channel.basic_publish.call_args
    assert call.kwargs["exchange"] == EXCHANGE_PLUGINS
    assert call.kwargs["routing_key"] == "magellon.plugins.config.broadcast"


# -- subscribe_events -----------------------------------------------------

def test_subscribe_events_binds_anonymous_queue_with_translated_routing_key(binder, mock_client):
    queue_frame = MagicMock()
    queue_frame.method.queue = "amq.gen-ABC123"
    # The subscribe path uses a fresh client; configure the next one:
    # the side_effect in the fixture creates a fresh MagicMock; grab it
    # post-hoc.
    binder.subscribe_events(
        HeartbeatRoute.all(), lambda env: None
    )
    handle = binder._subscriber_handles[-1]
    client = handle._client

    # subscribe declared an anonymous queue
    decl_call = client.channel.queue_declare.call_args
    assert decl_call.kwargs == {"queue": "", "exclusive": True, "auto_delete": True}
    # bound with > → # translation
    bind_call = client.channel.queue_bind.call_args
    assert bind_call.kwargs["exchange"] == EXCHANGE_PLUGINS
    assert bind_call.kwargs["routing_key"] == "magellon.plugins.heartbeat.#"


def test_subscribe_events_decodes_envelope_and_invokes_handler(binder):
    received = []
    binder.subscribe_events(HeartbeatRoute.all(), received.append)
    handle = binder._subscriber_handles[-1]
    client = handle._client

    # Pull out the callback passed to basic_consume
    consume_call = client.channel.basic_consume.call_args
    callback = consume_call.kwargs["on_message_callback"]

    # Drive the callback with an envelope on the wire
    env = _env({"status": "ready"})
    callback(MagicMock(), MagicMock(routing_key="magellon.plugins.heartbeat.ctf.x"), None, env.model_dump_json().encode())

    assert len(received) == 1
    assert received[0].data == {"status": "ready"}


def test_subscribe_events_swallows_handler_exceptions(binder):
    """A broken event handler must not crash the consumer thread."""
    def broken(env):
        raise RuntimeError("kaboom")

    binder.subscribe_events(HeartbeatRoute.all(), broken)
    handle = binder._subscriber_handles[-1]
    client = handle._client
    callback = client.channel.basic_consume.call_args.kwargs["on_message_callback"]

    # Must not raise
    callback(MagicMock(), MagicMock(routing_key="x"), None, _env({}).model_dump_json().encode())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(data: dict) -> Envelope:
    return Envelope.wrap(
        source="magellon/tests",
        type="magellon.test",
        subject="test",
        data=data,
    )


def _ch_method_props(*, headers=None):
    ch = MagicMock()
    method = MagicMock()
    method.delivery_tag = 42
    method.redelivered = False
    properties = MagicMock()
    properties.headers = headers
    return ch, method, properties

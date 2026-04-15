"""Unit tests for ``magellon_sdk.transport.rabbitmq_events``.

The publisher is sync pika, so we don't need a real broker — we mock
``pika.BlockingConnection`` and assert the calls. The consumer's
threading + blocking ``start_consuming`` is harder to drive in a
unit test; we cover the message-decoding callback path by extracting
it via the same factory pattern. A live integration test belongs
under the CoreService integration suite, gated by RMQ availability.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pika

from magellon_sdk.envelope import Envelope
from magellon_sdk.transport.rabbitmq_events import (
    DEFAULT_EXCHANGE,
    RabbitmqEventConsumer,
    RabbitmqEventPublisher,
    step_routing_key,
)


def _settings():
    return SimpleNamespace(
        HOST_NAME="localhost",
        USER_NAME="guest",
        PASSWORD="guest",
    )


def _envelope():
    return Envelope.wrap(
        source="magellon/plugins/ctf",
        type="magellon.step.completed",
        subject="magellon.job.x.step.ctf",
        data={"job_id": str(uuid4()), "step": "ctf"},
    )


def test_step_routing_key_uses_dot_separated_form():
    """Topic exchanges expect dotted keys for wildcard matching."""
    job_id = uuid4()
    assert step_routing_key(job_id, "ctf") == f"job.{job_id}.step.ctf"


def test_publisher_declares_topic_exchange_on_connect():
    fake_channel = MagicMock()
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.channel.return_value = fake_channel

    with patch.object(pika, "BlockingConnection", return_value=fake_conn):
        pub = RabbitmqEventPublisher(_settings())
        pub.connect()

    fake_channel.exchange_declare.assert_called_once_with(
        exchange=DEFAULT_EXCHANGE, exchange_type="topic", durable=True
    )


def test_publisher_publish_sets_cloudevents_correlation():
    """``message_id`` must equal envelope id so dedup tooling on the
    broker side has the same correlation key as the DB writer."""
    fake_channel = MagicMock()
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.channel.return_value = fake_channel

    with patch.object(pika, "BlockingConnection", return_value=fake_conn):
        pub = RabbitmqEventPublisher(_settings())
        pub.connect()
        env = _envelope()
        pub.publish("job.abc.step.ctf", env)

    args, kwargs = fake_channel.basic_publish.call_args
    assert kwargs["exchange"] == DEFAULT_EXCHANGE
    assert kwargs["routing_key"] == "job.abc.step.ctf"
    props = kwargs["properties"]
    assert props.message_id == env.id
    assert props.type == env.type
    assert props.delivery_mode == 2
    # Body must round-trip back to the same envelope.
    decoded = Envelope.model_validate_json(kwargs["body"])
    assert decoded.id == env.id


def test_publisher_connect_is_idempotent():
    fake_channel = MagicMock()
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.channel.return_value = fake_channel

    with patch.object(pika, "BlockingConnection", return_value=fake_conn) as new_conn:
        pub = RabbitmqEventPublisher(_settings())
        pub.connect()
        pub.connect()

    new_conn.assert_called_once()


def test_publisher_publish_auto_connects_when_idle():
    """publish() now self-heals: if no live channel exists it opens one
    before publishing. This is the first half of the idle-disconnect
    fix — callers don't have to remember to connect()."""
    fake_channel = MagicMock()
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.channel.return_value = fake_channel

    with patch.object(pika, "BlockingConnection", return_value=fake_conn) as new_conn:
        pub = RabbitmqEventPublisher(_settings())
        pub.publish("job.x.step.ctf", _envelope())

    new_conn.assert_called_once()
    fake_channel.basic_publish.assert_called_once()


def test_publisher_reconnects_once_when_stream_lost_mid_publish():
    """The bug we hit on the FFT plugin: pika's BlockingConnection drops
    the channel after idle, then every subsequent basic_publish raises
    StreamLostError forever. The publisher must reconnect once and retry
    so a transient broker hiccup doesn't kill the mirror permanently."""
    from pika.exceptions import StreamLostError

    healthy_channel_1 = MagicMock()
    healthy_conn_1 = MagicMock()
    healthy_conn_1.is_closed = False
    healthy_conn_1.channel.return_value = healthy_channel_1

    healthy_channel_2 = MagicMock()
    healthy_conn_2 = MagicMock()
    healthy_conn_2.is_closed = False
    healthy_conn_2.channel.return_value = healthy_channel_2

    # First basic_publish dies with the same error pika raises on idle drop.
    # Second one (after reconnect) succeeds.
    healthy_channel_1.basic_publish.side_effect = StreamLostError(
        "Stream connection lost: ConnectionResetError(104, 'Connection reset by peer')"
    )

    with patch.object(
        pika, "BlockingConnection",
        side_effect=[healthy_conn_1, healthy_conn_2],
    ) as new_conn:
        pub = RabbitmqEventPublisher(_settings())
        pub.connect()
        pub.publish("job.x.step.ctf", _envelope())

    # Two physical connections opened: one initial, one after the failure.
    assert new_conn.call_count == 2
    # And the second channel saw the retried publish.
    healthy_channel_2.basic_publish.assert_called_once()


def test_publisher_uses_heartbeat_to_keep_idle_connection_alive():
    """Without heartbeat the broker drops the socket on idle. We pass
    heartbeat=30 + blocked_connection_timeout=300 to make the connection
    survive long quiet periods between batches."""
    fake_channel = MagicMock()
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    fake_conn.channel.return_value = fake_channel

    with patch.object(pika, "BlockingConnection", return_value=fake_conn) as new_conn:
        with patch.object(pika, "ConnectionParameters", wraps=pika.ConnectionParameters) as new_params:
            pub = RabbitmqEventPublisher(_settings())
            pub.connect()

    new_conn.assert_called_once()
    _, kwargs = new_params.call_args
    assert kwargs.get("heartbeat") == 30
    assert kwargs.get("blocked_connection_timeout") == 300


def test_consumer_binding_defaults_to_step_wildcard():
    """Default binding catches every step on every job — that's what
    the CoreService forwarder wants. Check the args without starting
    the thread."""
    consumer = RabbitmqEventConsumer(_settings(), queue_name="q-test")
    assert consumer.binding_key == "job.*.step.*"
    assert consumer.exchange == DEFAULT_EXCHANGE
    assert consumer.queue_name == "q-test"

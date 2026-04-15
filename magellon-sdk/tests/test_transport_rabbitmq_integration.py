"""Integration tests for magellon_sdk.transport.rabbitmq.

Requires a real RabbitMQ broker reachable at ``RABBITMQ_URL``
(default ``amqp://rabbit:behd1d2@127.0.0.1:5672/``). Start with::

    docker compose -f Docker/docker-compose.yml up rabbitmq -d

Tests are skipped cleanly when the broker is not reachable. Every
test uses a unique queue name so runs don't collide.
"""
from __future__ import annotations

import os
import socket
import uuid

import pytest

pika = pytest.importorskip("pika")
from pika.exceptions import AMQPConnectionError

from magellon_sdk import messaging
from magellon_sdk.models import TaskDto
from magellon_sdk.transport.rabbitmq import RabbitmqClient


RMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RABBITMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RABBITMQ_PASS", "behd1d2")


class _Settings:
    HOST_NAME = RMQ_HOST
    PORT = RMQ_PORT
    USER_NAME = RMQ_USER
    PASSWORD = RMQ_PASS
    QUEUE_NAME = "rmq-integration-default"


def _broker_reachable() -> bool:
    try:
        with socket.create_connection((RMQ_HOST, RMQ_PORT), timeout=2):
            pass
        # Also confirm AMQP handshake — port open != RMQ ready.
        params = pika.ConnectionParameters(
            host=RMQ_HOST,
            credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
            socket_timeout=2,
            connection_attempts=1,
        )
        conn = pika.BlockingConnection(params)
        conn.close()
        return True
    except Exception:
        return False


def _unique_queue() -> str:
    return f"rmq-test-{uuid.uuid4().hex[:8]}"


def _delete_queue(q: str) -> None:
    params = pika.ConnectionParameters(
        host=RMQ_HOST,
        credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
    )
    conn = pika.BlockingConnection(params)
    try:
        ch = conn.channel()
        ch.queue_delete(queue=q)
    finally:
        conn.close()


@pytest.fixture(scope="module", autouse=True)
def _require_broker():
    if not _broker_reachable():
        pytest.skip(f"RabbitMQ not reachable at {RMQ_HOST}:{RMQ_PORT}")


def test_publish_round_trip():
    q = _unique_queue()
    try:
        client = RabbitmqClient(_Settings())
        client.connect()
        try:
            client.publish_message("hello", queue_name=q)
        finally:
            client.close_connection()

        # Independent consumer verifies the message landed.
        params = pika.ConnectionParameters(
            host=RMQ_HOST,
            credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        )
        conn = pika.BlockingConnection(params)
        try:
            ch = conn.channel()
            ch.queue_declare(queue=q, durable=True)
            method, _, body = ch.basic_get(queue=q, auto_ack=True)
            assert method is not None, "no message received from queue"
            assert body == b"hello"
        finally:
            conn.close()
    finally:
        _delete_queue(q)


def test_connect_raises_on_bad_host():
    """connect() previously swallowed AMQPConnectionError and left
    self.connection = None, so the next publish_message() raised
    AttributeError. Now it raises the underlying error so the caller
    can distinguish 'cannot connect' from 'published'."""
    class _BadSettings:
        HOST_NAME = "127.0.0.1"
        PORT = 1  # nothing listens on port 1
        USER_NAME = "x"
        PASSWORD = "x"

    client = RabbitmqClient(_BadSettings())
    with pytest.raises(AMQPConnectionError):
        client.connect()


def test_publish_message_to_queue_helper_success():
    q = _unique_queue()
    try:
        task = TaskDto(data={"k": "v"})
        ok = messaging.publish_message_to_queue(task, q, rabbitmq_settings=_Settings())
        assert ok is True

        # Confirm the body round-trips via TaskDto.
        params = pika.ConnectionParameters(
            host=RMQ_HOST,
            credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        )
        conn = pika.BlockingConnection(params)
        try:
            ch = conn.channel()
            ch.queue_declare(queue=q, durable=True)
            method, _, body = ch.basic_get(queue=q, auto_ack=True)
            assert method is not None
            restored = messaging.parse_message_to_task_object(body.decode())
            assert restored.data == {"k": "v"}
        finally:
            conn.close()
    finally:
        _delete_queue(q)


def test_publish_message_to_queue_returns_false_on_bad_broker():
    """Previously: connect() swallowed errors -> publish appeared to
    succeed -> helper returned True. Now helper returns False because
    connect() raises."""
    class _BadSettings:
        HOST_NAME = "127.0.0.1"
        PORT = 1
        USER_NAME = "x"
        PASSWORD = "x"

    task = TaskDto(data={"k": "v"})
    ok = messaging.publish_message_to_queue(task, "any-queue", rabbitmq_settings=_BadSettings())
    assert ok is False

"""Integration tests for magellon_sdk.transport.nats.

These exercise the publisher/consumer pair against a real NATS broker.
Each test owns a unique stream + subject + durable-name so runs never
collide. Tests skip cleanly if NATS is not reachable; start the broker
with::

    docker compose -f Docker/docker-compose.yml up nats -d
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

nats = pytest.importorskip("nats")

from magellon_sdk.envelope import Envelope
from magellon_sdk.transport.nats import NatsConsumer, NatsPublisher

pytestmark = pytest.mark.asyncio

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
TEST_BUDGET = 30  # seconds — guards against consumer-loop hangs


async def _nats_reachable() -> bool:
    try:
        nc = await asyncio.wait_for(nats.connect(NATS_URL), timeout=2)
    except Exception:
        return False
    await nc.close()
    return True


def _unique_stream() -> tuple[str, str, str]:
    tag = uuid.uuid4().hex[:8]
    return f"SDK_TEST_{tag}", f"sdk.test.{tag}", f"sdk-consumer-{tag}"


async def _delete_stream(stream: str) -> None:
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    try:
        await js.delete_stream(stream)
    except Exception:
        pass
    await nc.close()


async def _wait_for(predicate, seconds: float) -> bool:
    deadline = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


async def _round_trip():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")

    stream, subject, durable = _unique_stream()
    try:
        pub = NatsPublisher(NATS_URL, stream=stream, subjects=[subject])
        await pub.connect()

        con = NatsConsumer(NATS_URL, stream=stream, subject=subject, durable_name=durable)
        assert await con.connect() is True

        received: list = []

        async def _cb(env: Envelope):
            received.append(env)

        await con.subscribe(_cb)

        try:
            env = Envelope.wrap(
                source="sdk-tests",
                type="com.example.test",
                subject=f"sdk.test.{durable}",
                data={"n": 42, "msg": "hi"},
            )
            await pub.publish(subject, env)

            assert await _wait_for(lambda: len(received) >= 1, 5), (
                f"timed out waiting for envelope; received={received}"
            )
            got = received[0]
            assert got.id == env.id
            assert got.source == "sdk-tests"
            assert got.type == "com.example.test"
            assert got.data == {"n": 42, "msg": "hi"}
        finally:
            await con.close()
            await pub.close()
    finally:
        await _delete_stream(stream)


async def test_publisher_consumer_round_trip():
    await asyncio.wait_for(_round_trip(), timeout=TEST_BUDGET)


async def _order():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")

    stream, subject, durable = _unique_stream()
    try:
        pub = NatsPublisher(NATS_URL, stream=stream, subjects=[subject])
        await pub.connect()

        con = NatsConsumer(NATS_URL, stream=stream, subject=subject, durable_name=durable)
        assert await con.connect() is True

        received: list = []

        async def _cb(env: Envelope):
            received.append(env.data["n"])

        await con.subscribe(_cb)

        try:
            for n in range(5):
                await pub.publish(
                    subject,
                    Envelope.wrap(source="sdk-tests", type="t", data={"n": n}),
                )

            assert await _wait_for(lambda: len(received) >= 5, 10), (
                f"received {received} / 5"
            )
            assert received == [0, 1, 2, 3, 4]
        finally:
            await con.close()
            await pub.close()
    finally:
        await _delete_stream(stream)


async def test_publish_preserves_order():
    await asyncio.wait_for(_order(), timeout=TEST_BUDGET)


async def _missing_stream():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")

    stream, subject, durable = _unique_stream()
    con = NatsConsumer(NATS_URL, stream=stream, subject=subject, durable_name=durable)
    try:
        assert await con.connect() is False
    finally:
        await con.close()


async def test_consumer_connect_false_when_stream_missing():
    await asyncio.wait_for(_missing_stream(), timeout=TEST_BUDGET)


async def _publish_before_connect():
    stream, subject, durable = _unique_stream()
    pub = NatsPublisher(NATS_URL, stream=stream, subjects=[subject])
    with pytest.raises(RuntimeError, match="connect"):
        await pub.publish(subject, Envelope.wrap(source="s", type="t", data={}))


async def test_publish_without_connect_raises():
    await asyncio.wait_for(_publish_before_connect(), timeout=TEST_BUDGET)

"""NATS JetStream round-trip smoke test.

Exercises ``support/events/publisher.py::PublisherContext`` and
``support/events/subscriber.py::ConsumerContext`` against a real NATS
broker (``nats://localhost:4222``). These tests pin the current
contract so Phase 2's SDK extraction is a diff, not a guess.

Requirements:
- NATS container with JetStream enabled on 4222:
    docker compose -f Docker/docker-compose.yml up nats -d

Every test has a hard wall-clock budget (30s) so a broker hiccup or a
regressed consumer loop surfaces as a timeout failure rather than
hanging the suite.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid

import nats
import pytest

from support.events.publisher import PublisherContext
from support.events.subscriber import ConsumerContext

pytestmark = [pytest.mark.requires_docker, pytest.mark.asyncio]

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
STREAM = "EVENTS"
SUBJECT = "message-topic"
TEST_BUDGET = 30  # seconds — hard ceiling per test, guards against hangs


async def _nats_reachable() -> bool:
    try:
        nc = await asyncio.wait_for(nats.connect(NATS_URL), timeout=2)
    except Exception:
        return False
    await nc.close()
    return True


async def _reset_stream() -> None:
    """Delete the shared stream so publisher.connect() recreates it
    fresh. JetStream state persists across processes."""
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    try:
        await js.delete_stream(STREAM)
    except Exception:
        pass
    await nc.close()


async def _publish_event(pub: PublisherContext, payload: dict) -> str:
    event_id = str(uuid.uuid4())
    body = {
        "id": event_id,
        "source": "integration-test",
        "type": "com.example.test",
        "time": "2026-04-15T00:00:00+00:00",
        "specversion": "1.0",
        "data": payload,
    }
    await pub.js.publish(
        SUBJECT,
        json.dumps(body).encode(),
        headers={
            "ce-specversion": "1.0",
            "ce-id": event_id,
            "ce-source": "integration-test",
            "ce-type": "com.example.test",
            "content-type": "application/json",
        },
    )
    return event_id


async def _wait_for(predicate, deadline: float) -> bool:
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


async def _round_trip_impl():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")
    await _reset_stream()

    pub = PublisherContext(broker_url=NATS_URL)
    await pub.connect()

    consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
    con = ConsumerContext(NATS_URL, STREAM, consumer_name)
    connected = await con.connect()
    assert connected is True, "ConsumerContext.connect() should return True after publisher created the stream"

    received: list = []

    async def _cb(event):
        received.append({"id": event["id"], "data": event.data})

    await con.subscribe(_cb)

    try:
        event_id = await _publish_event(pub, {"message": "roundtrip"})
        deadline = asyncio.get_event_loop().time() + 5
        ok = await _wait_for(lambda: len(received) >= 1, deadline)
        assert ok, f"timed out waiting for message; received={received}"
        assert received[0]["id"] == event_id
        assert received[0]["data"] == {"message": "roundtrip"}
    finally:
        # Stop the consumer loop first, then close connections.
        con.running = False
        await con.close()
        await pub.close()


async def test_round_trip_single_message():
    await asyncio.wait_for(_round_trip_impl(), timeout=TEST_BUDGET)


async def _order_impl():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")
    await _reset_stream()

    pub = PublisherContext(broker_url=NATS_URL)
    await pub.connect()

    consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
    con = ConsumerContext(NATS_URL, STREAM, consumer_name)
    assert await con.connect() is True

    received: list = []

    async def _cb(event):
        received.append(event.data.get("n"))

    await con.subscribe(_cb)

    try:
        for n in range(5):
            await _publish_event(pub, {"n": n})

        deadline = asyncio.get_event_loop().time() + 10
        ok = await _wait_for(lambda: len(received) >= 5, deadline)
        assert ok, f"received {len(received)}/5: {received}"
        assert received == [0, 1, 2, 3, 4]
    finally:
        con.running = False
        await con.close()
        await pub.close()


async def test_round_trip_preserves_order():
    await asyncio.wait_for(_order_impl(), timeout=TEST_BUDGET)


async def _missing_stream_impl():
    if not await _nats_reachable():
        pytest.skip(f"NATS not reachable at {NATS_URL}")
    await _reset_stream()

    consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
    con = ConsumerContext(NATS_URL, STREAM, consumer_name)
    try:
        connected = await con.connect()
        assert connected is False
    finally:
        await con.close()


async def test_consumer_connect_false_when_stream_missing():
    """ConsumerContext.connect() must return False (not raise) when the
    stream doesn't exist yet — that's the signal the FastAPI startup
    retry loop depends on."""
    await asyncio.wait_for(_missing_stream_impl(), timeout=TEST_BUDGET)

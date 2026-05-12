"""Tests for core.plugin_log_stream — the Socket.IO follower bookkeeper.

Two surfaces:

  - PluginLogStreamer — subscriber bookkeeping + lifecycle of the
    follower task.
  - file_tail_follower / docker_logs_follower — the actual tail
    implementations.

Tests don't touch the real socketio_server; they pass a recording
``emit_line`` callable instead and assert on what got emitted.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.plugin_log_stream import (
    PluginLogStreamer,
    file_tail_follower,
    plugin_log_room,
)


def test_room_naming():
    assert plugin_log_room("fft") == "plugin:fft"


# ---------------------------------------------------------------------------
# Subscriber bookkeeping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streamer_starts_follower_on_first_subscriber():
    streamer = PluginLogStreamer()
    started = asyncio.Event()
    stop_received = asyncio.Event()

    async def factory(plugin_id, emit_line, stop_event):
        started.set()
        await stop_event.wait()
        stop_received.set()

    emit_calls: list = []

    async def emit(payload):
        emit_calls.append(payload)

    await streamer.subscribe("fft", "sid-1", emit, factory)

    # Factory was invoked.
    await asyncio.wait_for(started.wait(), timeout=1.0)
    assert streamer.has_subscribers("fft")

    # Unsubscribe → follower's stop_event is set.
    await streamer.unsubscribe("fft", "sid-1")
    await asyncio.wait_for(stop_received.wait(), timeout=1.0)
    assert not streamer.has_subscribers("fft")


@pytest.mark.asyncio
async def test_streamer_reuses_follower_for_second_subscriber():
    """Second sid joining shouldn't spawn a second follower task."""
    streamer = PluginLogStreamer()
    factory_calls = 0

    async def factory(plugin_id, emit_line, stop_event):
        nonlocal factory_calls
        factory_calls += 1
        await stop_event.wait()

    async def emit(payload):
        pass

    await streamer.subscribe("fft", "sid-1", emit, factory)
    await asyncio.sleep(0)  # let the spawned task run
    await streamer.subscribe("fft", "sid-2", emit, factory)
    await asyncio.sleep(0)
    assert factory_calls == 1

    # First leaves — follower should keep running.
    await streamer.unsubscribe("fft", "sid-1")
    assert streamer.has_subscribers("fft")
    assert factory_calls == 1

    # Last leaves — follower stops.
    await streamer.unsubscribe("fft", "sid-2")
    assert not streamer.has_subscribers("fft")


@pytest.mark.asyncio
async def test_streamer_unsubscribe_unknown_is_noop():
    """Disconnect handler may try to unsubscribe a sid that never
    joined. Must not raise."""
    streamer = PluginLogStreamer()
    await streamer.unsubscribe("fft", "never-joined-sid")
    # No assertion needed — just verify no exception.


# ---------------------------------------------------------------------------
# file_tail_follower
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_tail_follower_emits_appended_lines(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("preexisting line\n", encoding="utf-8")

    stop_event = asyncio.Event()
    emitted: list = []

    async def emit(payload):
        emitted.append(payload)

    task = asyncio.create_task(file_tail_follower(log, emit, stop_event))

    # Wait a tick so the tailer parks at EOF.
    await asyncio.sleep(0.3)

    # Append a line — should be picked up.
    with log.open("a", encoding="utf-8") as fh:
        fh.write("new line one\n")
        fh.write("new line two\n")
        fh.flush()

    # Poll for both lines.
    deadline = asyncio.get_event_loop().time() + 3.0
    while asyncio.get_event_loop().time() < deadline:
        if len([p for p in emitted if not p.get("error")]) >= 2:
            break
        await asyncio.sleep(0.1)

    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)

    lines = [p["line"] for p in emitted if not p.get("error")]
    assert "new line one" in lines
    assert "new line two" in lines


@pytest.mark.asyncio
async def test_file_tail_follower_warns_when_file_missing(tmp_path):
    """Plugin may not have been started yet — log file doesn't exist.
    The tailer should emit a one-shot error message rather than crash,
    and continue polling so it picks up when the file appears."""
    log = tmp_path / "never.log"
    stop_event = asyncio.Event()
    emitted: list = []

    async def emit(payload):
        emitted.append(payload)

    task = asyncio.create_task(file_tail_follower(log, emit, stop_event))
    await asyncio.sleep(0.4)
    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)

    assert any(p.get("error") for p in emitted), emitted


@pytest.mark.asyncio
async def test_file_tail_follower_handles_truncation(tmp_path):
    """Rotation / log truncation must not crash the tailer; instead it
    should reset position and pick up new content."""
    log = tmp_path / "app.log"
    log.write_text("line a\nline b\n", encoding="utf-8")

    stop_event = asyncio.Event()
    emitted: list = []

    async def emit(payload):
        emitted.append(payload)

    task = asyncio.create_task(file_tail_follower(log, emit, stop_event))
    await asyncio.sleep(0.3)

    # Truncate + rewrite.
    log.write_text("after rotate\n", encoding="utf-8")

    deadline = asyncio.get_event_loop().time() + 3.0
    while asyncio.get_event_loop().time() < deadline:
        if any(p.get("line") == "after rotate" for p in emitted):
            break
        await asyncio.sleep(0.1)

    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert any(p.get("line") == "after rotate" for p in emitted), emitted

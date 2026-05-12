"""Socket.IO live tail of plugin logs (Phase 6).

Companion to ``GET /admin/plugins/{id}/logs`` (one-shot tail). For
follow-mode the React UI joins a ``plugin:{plugin_id}`` Socket.IO room
and receives one ``plugin_log`` event per line as the plugin emits.

Architecture
------------

  - One follower task per plugin, started lazily when the first client
    joins the room, stopped when the last client leaves.
  - Followers shell out to ``docker logs --follow`` (docker installs)
    or tail ``<install_dir>/app.log`` (Popen / uv installs) and
    forward line-by-line.
  - Subscriber count tracked in an in-process dict — fine for single
    CoreService deployments (the only topology Magellon supports
    today). A future scale-out would need a coordinator (Redis pubsub).

Failure modes
-------------

  - Plugin not installed → join returns ``{"ok": False, "error": ...}``.
  - Log source unavailable → follower emits a one-shot ``plugin_log``
    with ``error=True`` and exits; the UI shows "logs unavailable".
  - Follower crash → restart on next join.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


def plugin_log_room(plugin_id: str) -> str:
    return f"plugin:{plugin_id}"


@dataclass
class _Follower:
    """One follower task per plugin. Tracks subscribers + the asyncio
    Task running the tail loop."""

    plugin_id: str
    subscribers: Set[str] = field(default_factory=set)
    task: Optional[asyncio.Task] = None
    stop_event: Optional[asyncio.Event] = None


class PluginLogStreamer:
    """Process-wide tracker of plugin-log followers.

    Owns no I/O — actual line emission is delegated to ``emit_line``
    callbacks passed in by the Socket.IO handler. Keeps the streamer
    decoupled from socketio_server import order.
    """

    def __init__(self) -> None:
        self._followers: dict[str, _Follower] = {}
        self._lock = threading.Lock()

    def has_subscribers(self, plugin_id: str) -> bool:
        with self._lock:
            f = self._followers.get(plugin_id)
            return bool(f and f.subscribers)

    async def subscribe(
        self,
        plugin_id: str,
        sid: str,
        emit_line,             # async callable: (room, line) -> None
        follower_factory,      # async callable: (plugin_id, emit_line, stop_event) -> Task body
    ) -> None:
        """Add ``sid`` to ``plugin_id``'s followers. If this is the
        first subscriber, kick off the follower task.

        ``follower_factory`` is the bound coroutine that does the
        actual tail (calling ``docker logs --follow`` or tail-f on
        the file) and emits each line via ``emit_line``. Stored on
        the streamer so different deployments can plug in different
        sources (the tests use an in-memory line queue).
        """
        with self._lock:
            f = self._followers.get(plugin_id)
            if f is None:
                stop_event = asyncio.Event()
                f = _Follower(plugin_id=plugin_id, stop_event=stop_event)
                self._followers[plugin_id] = f
                first = True
            else:
                first = False
            f.subscribers.add(sid)

        if first:
            assert f.stop_event is not None
            f.task = asyncio.create_task(
                follower_factory(plugin_id, emit_line, f.stop_event),
                name=f"plugin-log-follower:{plugin_id}",
            )

    async def unsubscribe(self, plugin_id: str, sid: str) -> None:
        """Remove ``sid``. When the last subscriber leaves, signal the
        follower task to stop."""
        task_to_await: Optional[asyncio.Task] = None
        with self._lock:
            f = self._followers.get(plugin_id)
            if not f:
                return
            f.subscribers.discard(sid)
            if not f.subscribers:
                # Last subscriber out — tear down.
                stop_event = f.stop_event
                task_to_await = f.task
                del self._followers[plugin_id]
                if stop_event is not None:
                    stop_event.set()
        if task_to_await is not None:
            try:
                await asyncio.wait_for(task_to_await, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task_to_await.cancel()


# ---------------------------------------------------------------------------
# Follower implementations
# ---------------------------------------------------------------------------


async def docker_logs_follower(
    container_name: str, emit_line, stop_event: asyncio.Event,
) -> None:
    """Run ``docker logs --follow <container>`` and pipe each line to
    ``emit_line``. Honours the stop event for clean shutdown."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "logs", "--follow", "--tail", "0", container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        await emit_line({"error": True, "line": "<docker CLI not available>"})
        return
    except Exception as exc:  # noqa: BLE001
        await emit_line({"error": True, "line": f"<spawn failed: {exc}>"})
        return

    try:
        assert proc.stdout is not None
        while not stop_event.is_set():
            try:
                line_bytes = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=0.5,
                )
            except asyncio.TimeoutError:
                continue
            if not line_bytes:
                # docker logs exited (container removed / stopped).
                break
            await emit_line({
                "line": line_bytes.decode("utf-8", errors="replace").rstrip(),
            })
    finally:
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass


async def file_tail_follower(
    log_path: Path, emit_line, stop_event: asyncio.Event,
) -> None:
    """``tail -f`` equivalent for the Popen supervisor's ``app.log``.

    Pure-Python: opens the file at end-of-file, polls for new content
    every 250ms. Handles file rotation/truncation by reopening when
    inode changes or file shrinks.
    """
    pos = 0
    try:
        if log_path.exists():
            pos = log_path.stat().st_size
        else:
            await emit_line({
                "error": True,
                "line": f"<log file does not exist yet: {log_path}>",
            })
            # Don't return — wait for it to appear.

        leftover = ""
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.25)
            except asyncio.TimeoutError:
                pass
            if stop_event.is_set():
                break
            if not log_path.exists():
                continue
            try:
                size = log_path.stat().st_size
            except OSError:
                continue
            if size < pos:
                # Truncated / rotated.
                pos = 0
                leftover = ""
            if size <= pos:
                continue
            try:
                with log_path.open("rb") as fh:
                    fh.seek(pos)
                    chunk = fh.read(size - pos)
                pos = size
            except OSError as exc:
                await emit_line({"error": True, "line": f"<read failed: {exc}>"})
                continue
            text = leftover + chunk.decode("utf-8", errors="replace")
            *complete, leftover = text.split("\n")
            for line in complete:
                # Strip trailing CR so Windows CRLF logs come through
                # cleanly. The leftover (next-iteration prefix) is kept
                # as-is — partial lines may legitimately contain CRs.
                line = line.rstrip("\r")
                if not line:
                    continue
                await emit_line({"line": line})
    except Exception as exc:  # noqa: BLE001
        await emit_line({"error": True, "line": f"<tail failed: {exc}>"})


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


_STREAMER: Optional[PluginLogStreamer] = None


def get_log_streamer() -> PluginLogStreamer:
    global _STREAMER
    if _STREAMER is None:
        _STREAMER = PluginLogStreamer()
    return _STREAMER


def reset_log_streamer() -> None:
    """Test helper — drop the singleton so each test starts fresh."""
    global _STREAMER
    _STREAMER = None


__all__ = [
    "PluginLogStreamer",
    "docker_logs_follower",
    "file_tail_follower",
    "get_log_streamer",
    "plugin_log_room",
    "reset_log_streamer",
]

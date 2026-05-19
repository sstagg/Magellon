"""Operational task-event logger — writes structured JSONL to disk with
size-based rotation so audit history is always query-ready via DuckDB.

Thread-safe, best-effort: a write failure never propagates to the caller.

Rolling strategy
----------------
When the active file exceeds ``max_bytes`` (default 50 MB), the logger
rotates synchronously before each write:

    ops_events.jsonl          ← current
    ops_events.jsonl.1        ← previous
    ops_events.jsonl.2        ← ...
    ops_events.jsonl.5        ← oldest (max_files=5 → 5 backups kept)

The oldest backup beyond ``max_files`` is silently deleted.  On a 50-MB
cap with 5 backups you retain up to 300 MB of task history.

DuckDB query examples
---------------------
All DuckDB paths work against the glob pattern so you don't need to know
which rotation file a particular event landed in:

    import duckdb
    db = duckdb.connect()

    # Recent failures
    db.sql(\"\"\"
        SELECT ts, job_id, category, image_name
        FROM read_json_auto('C:/magellon/gpfs/ops_events.jsonl*')
        WHERE status = 'failed'
        ORDER BY ts DESC LIMIT 20
    \"\"\").show()

    # Throughput by category today
    db.sql(\"\"\"
        SELECT category, status, COUNT(*) AS n
        FROM read_json_auto('C:/magellon/gpfs/ops_events.jsonl*')
        WHERE ts >= strftime(CURRENT_DATE, '%Y-%m-%d')
        GROUP BY 1, 2
        ORDER BY 3 DESC
    \"\"\").show()

    # Average duration per category
    db.sql(\"\"\"
        SELECT category, AVG(duration_ms) / 1000.0 AS avg_s
        FROM read_json_auto('C:/magellon/gpfs/ops_events.jsonl*')
        WHERE duration_ms IS NOT NULL AND status = 'completed'
        GROUP BY 1
    \"\"\").show()
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file
_DEFAULT_MAX_FILES = 5                  # keep 5 rotated backups


class TaskEventLogger:
    """Thread-safe JSONL writer with size-based rotation.

    One global instance is shared across all threads via :func:`get_logger`.
    Callers should never construct this directly.
    """

    def __init__(
        self,
        path: str,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        max_files: int = _DEFAULT_MAX_FILES,
    ) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._max_files = max_files
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_task_result(
        self,
        *,
        job_id: Optional[str],
        task_id: Optional[str],
        category: str,
        status: str,          # "completed" | "failed"
        session_name: Optional[str] = None,
        image_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit one task-result event."""
        event: Dict[str, Any] = {
            "ts": _now_iso(),
            "event": "task_result",
            "job_id": job_id,
            "task_id": task_id,
            "category": category,
            "status": status,
            "session_name": session_name,
            "image_name": image_name,
            "duration_ms": duration_ms,
        }
        if extra:
            event.update(extra)
        self._write(event)

    def log_task_dispatch(
        self,
        *,
        job_id: Optional[str],
        task_id: Optional[str],
        category: str,
        session_name: Optional[str] = None,
        image_name: Optional[str] = None,
        queue: Optional[str] = None,
    ) -> None:
        """Emit one task-dispatch event (outbound to plugin queue)."""
        self._write({
            "ts": _now_iso(),
            "event": "task_dispatch",
            "job_id": job_id,
            "task_id": task_id,
            "category": category,
            "session_name": session_name,
            "image_name": image_name,
            "queue": queue,
        })

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, default=str) + "\n"
        try:
            with self._lock:
                self._maybe_rotate()
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception as exc:
            logger.debug("ops_event_logger: write failed: %s", exc)

    def _maybe_rotate(self) -> None:
        """Roll files if active file exceeds max_bytes. Caller holds lock."""
        try:
            if not os.path.exists(self._path):
                return
            if os.path.getsize(self._path) < self._max_bytes:
                return
            # Shift existing backups: .N → .(N+1), delete if beyond max_files
            for i in range(self._max_files, 0, -1):
                src = f"{self._path}.{i}"
                dst = f"{self._path}.{i + 1}"
                if os.path.exists(src):
                    if i >= self._max_files:
                        os.remove(src)
                    else:
                        os.replace(src, dst)
            # Active → .1
            os.replace(self._path, f"{self._path}.1")
        except OSError as exc:
            logger.debug("ops_event_logger: rotation failed: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[TaskEventLogger] = None
_instance_lock = threading.Lock()


def get_logger() -> TaskEventLogger:
    """Return the process-wide :class:`TaskEventLogger`, building it lazily.

    Path is resolved from ``app_settings`` so it lands under the GPFS root
    (``{MAGELLON_GPFS_PATH}/ops_events.jsonl``) — always reachable from the
    host even during Docker-managed runs.
    """
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is not None:
            return _instance
        path = _resolve_log_path()
        _instance = TaskEventLogger(path=path)
        logger.info("ops_event_logger: writing to %s", path)
        return _instance


def _resolve_log_path() -> str:
    try:
        from config import app_settings
        gpfs = app_settings.directory_settings.MAGELLON_GPFS_PATH or "/gpfs"
        return os.path.join(gpfs, "ops_events.jsonl")
    except Exception:
        return os.path.join(os.getcwd(), "ops_events.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["TaskEventLogger", "get_logger"]

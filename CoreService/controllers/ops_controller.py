"""REST endpoints for the operational event log (DuckDB / JSONL).

Mounted at /web/ops by main.py.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role

logger = logging.getLogger(__name__)

ops_router = APIRouter(
    dependencies=[
        Depends(get_current_user_id),
        Depends(require_role("Administrator")),
    ]
)


def _log_glob() -> str:
    """Return the glob pattern that covers all rotation files."""
    try:
        from core.AppSettings import AppSettingsSingleton
        app_settings = AppSettingsSingleton.get_instance()
        gpfs = app_settings.directory_settings.MAGELLON_GPFS_PATH or "/gpfs"
    except Exception:
        gpfs = os.environ.get("MAGELLON_GPFS_PATH", "C:/magellon/gpfs")
    return os.path.join(gpfs, "ops_events.jsonl*").replace("\\", "/")


def _run_duck(sql: str) -> List[Dict[str, Any]]:
    """Execute *sql* against the ops log and return rows as dicts."""
    import glob as _glob
    if not _glob.glob(_log_glob()):
        return []
    try:
        import duckdb
        con = duckdb.connect()
        rel = con.execute(sql)
        cols = [d[0] for d in rel.description]
        rows = rel.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    except ImportError:
        raise HTTPException(status_code=503, detail="duckdb package not installed on server")
    except Exception as exc:
        logger.error("DuckDB query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Response models ──────────────────────────────────────────────────────────

class SummaryRow(BaseModel):
    category: str
    status: str
    n: int
    first_seen: Optional[str]
    last_seen: Optional[str]
    avg_s: Optional[float]


class EventRow(BaseModel):
    ts: Optional[str]
    event: Optional[str]
    category: Optional[str]
    status: Optional[str]
    session_name: Optional[str]
    image_name: Optional[str]
    job_id: Optional[str]
    task_id: Optional[str]
    duration_ms: Optional[float]
    processor_error: Optional[str]
    queue: Optional[str]


class OpsLogInfo(BaseModel):
    log_glob: str
    file_count: int
    total_size_mb: float


# ── Endpoints ────────────────────────────────────────────────────────────────

@ops_router.get("/info", response_model=OpsLogInfo)
def get_ops_info():
    """Basic info about the ops log files on disk."""
    import glob as _glob
    pattern = _log_glob()
    files = _glob.glob(pattern)
    total = sum(os.path.getsize(f) for f in files if os.path.exists(f))
    return OpsLogInfo(
        log_glob=pattern,
        file_count=len(files),
        total_size_mb=round(total / 1_048_576, 2),
    )


@ops_router.get("/summary", response_model=List[SummaryRow])
def get_ops_summary():
    """Category × status breakdown with counts and avg duration."""
    glob = _log_glob()
    # ``MIN(ts) / MAX(ts)`` come back as datetime objects; the
    # SummaryRow model declares them as Optional[str] so the React
    # side can pass them straight into ``new Date(...)``. Cast to
    # ISO via ``strftime`` so Pydantic accepts the value.
    rows = _run_duck(f"""
        SELECT
            COALESCE(category, '?') AS category,
            COALESCE(status,   '?') AS status,
            COUNT(*)                AS n,
            strftime(MIN(CAST(ts AS TIMESTAMP)), '%Y-%m-%dT%H:%M:%S') AS first_seen,
            strftime(MAX(CAST(ts AS TIMESTAMP)), '%Y-%m-%dT%H:%M:%S') AS last_seen,
            ROUND(AVG(TRY_CAST(duration_ms AS DOUBLE)) / 1000.0, 2) AS avg_s
        FROM read_json_auto('{glob}', ignore_errors=true)
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)
    return [SummaryRow(**r) for r in rows]


# Columns the JSONL log carries today. ``processor_error`` and
# ``queue`` are reserved in the response model for future writers,
# but the SQL must emit NULL placeholders rather than reference the
# names — DuckDB binds names against the inferred schema and 500s if
# a referenced column never appears in any record.
_EVENT_SELECT = """
    strftime(CAST(ts AS TIMESTAMP), '%Y-%m-%dT%H:%M:%S') AS ts,
    event, category, status,
    session_name, image_name,
    CAST(job_id  AS VARCHAR) AS job_id,
    CAST(task_id AS VARCHAR) AS task_id,
    TRY_CAST(duration_ms AS DOUBLE) AS duration_ms,
    CAST(NULL AS VARCHAR) AS processor_error,
    CAST(NULL AS VARCHAR) AS queue
"""


@ops_router.get("/recent", response_model=List[EventRow])
def get_ops_recent(limit: int = Query(50, ge=1, le=500)):
    """Most recent N events across all categories."""
    glob = _log_glob()
    rows = _run_duck(f"""
        SELECT {_EVENT_SELECT}
        FROM read_json_auto('{glob}', ignore_errors=true)
        ORDER BY ts DESC
        LIMIT {limit}
    """)
    return [EventRow(**r) for r in rows]


@ops_router.get("/failed", response_model=List[EventRow])
def get_ops_failed(limit: int = Query(100, ge=1, le=1000)):
    """All failed task events, newest first."""
    glob = _log_glob()
    rows = _run_duck(f"""
        SELECT {_EVENT_SELECT}
        FROM read_json_auto('{glob}', ignore_errors=true)
        WHERE status = 'failed'
        ORDER BY ts DESC
        LIMIT {limit}
    """)
    return [EventRow(**r) for r in rows]


@ops_router.get("/category/{category}", response_model=List[EventRow])
def get_ops_by_category(
    category: str,
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
):
    """Events for a specific category, optionally filtered by status."""
    glob = _log_glob()
    where = f"WHERE lower(category) = lower('{category}')"
    if status:
        where += f" AND status = '{status}'"
    rows = _run_duck(f"""
        SELECT {_EVENT_SELECT}
        FROM read_json_auto('{glob}', ignore_errors=true)
        {where}
        ORDER BY ts DESC
        LIMIT {limit}
    """)
    return [EventRow(**r) for r in rows]


@ops_router.get("/throughput")
def get_ops_throughput():
    """Events per hour for the last 24 hours, grouped by category."""
    glob = _log_glob()
    # Comparing the raw ``ts`` column (VARCHAR or TIMESTAMP depending
    # on what DuckDB inferred) to a strftime'd VARCHAR errored with
    # "Cannot compare values of type TIMESTAMP and type VARCHAR".
    # Cast both sides to TIMESTAMP explicitly.
    rows = _run_duck(f"""
        SELECT
            strftime(CAST(ts AS TIMESTAMP), '%Y-%m-%dT%H:00') AS hour,
            COALESCE(category, '?') AS category,
            COUNT(*) AS n
        FROM read_json_auto('{glob}', ignore_errors=true)
        WHERE CAST(ts AS TIMESTAMP) >= NOW() - INTERVAL 24 HOURS
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)
    return rows

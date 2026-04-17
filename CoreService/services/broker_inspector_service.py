"""Broker inspection — projects RMQ Management API state into Magellon's
domain (per-pipeline tiles, plugin liveness join).

The page that consumes this is *not* a generic queue browser — it
answers one question: "is my Magellon pipeline healthy right now?"
That's why the response is shaped around the three live categories
(CTF / MotionCor / FFT) and joins broker depth/consumer counts with
the plugin liveness registry, rather than dumping every queue the
broker knows about. For a full broker browser, point operators at
the built-in Management UI on :15672.

Single network call: ``GET /api/queues`` returns every queue in one
payload, then we filter to the queues we care about. Keeps p99 latency
tight even with a slow broker. No client-side caching here — the
controller polls every 5s and the API call is cheap.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.plugin_liveness_registry import get_registry
from models.pydantic_models_settings import RabbitMQSettings

logger = logging.getLogger(__name__)


_DEFAULT_MGMT_PORT = 15672
_HTTP_TIMEOUT_S = 3.0


@dataclass(frozen=True)
class _Pipeline:
    """Static description of a Magellon pipeline → its RMQ queues."""
    name: str
    task_queue_attr: str
    result_queue_attr: str


_PIPELINES: List[_Pipeline] = [
    _Pipeline("CTF", "CTF_QUEUE_NAME", "CTF_OUT_QUEUE_NAME"),
    _Pipeline("MotionCor", "MOTIONCOR_QUEUE_NAME", "MOTIONCOR_OUT_QUEUE_NAME"),
    _Pipeline("FFT", "FFT_QUEUE_NAME", "FFT_OUT_QUEUE_NAME"),
]


def _mgmt_port() -> int:
    raw = os.environ.get("MAGELLON_RMQ_MGMT_PORT")
    if raw:
        try:
            return int(raw)
        except ValueError:
            logger.warning("MAGELLON_RMQ_MGMT_PORT=%r is not int — falling back to 15672", raw)
    return _DEFAULT_MGMT_PORT


def _vhost_path(vhost: Optional[str]) -> str:
    # Default vhost "/" must be URL-encoded as %2F in management API paths.
    raw = vhost or "/"
    return "%2F" if raw == "/" else raw.lstrip("/").replace("/", "%2F")


def _fetch_queues(settings: RabbitMQSettings) -> List[Dict[str, Any]]:
    host = settings.HOST_NAME or "localhost"
    port = _mgmt_port()
    user = settings.USER_NAME or "guest"
    pw = settings.PASSWORD or "guest"
    vhost = _vhost_path(settings.VIRTUAL_HOST)
    url = f"http://{host}:{port}/api/queues/{vhost}"

    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    req = Request(url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    with urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def _project_queue(name: Optional[str], queues_by_name: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Project one queue dict from the management payload into the tile shape.

    Returns ``exists=False`` when the queue hasn't been declared yet —
    common in dev before any task has been published. Rates default to
    0 when the broker hasn't started reporting them.
    """
    if not name:
        return {"name": None, "exists": False, "depth": 0, "consumers": 0,
                "publish_rate": 0.0, "deliver_rate": 0.0}
    q = queues_by_name.get(name)
    if q is None:
        return {"name": name, "exists": False, "depth": 0, "consumers": 0,
                "publish_rate": 0.0, "deliver_rate": 0.0}

    msg_stats = q.get("message_stats") or {}
    publish_details = (msg_stats.get("publish_details") or {})
    deliver_details = (msg_stats.get("deliver_get_details") or {})
    return {
        "name": name,
        "exists": True,
        "depth": int(q.get("messages") or 0),
        "consumers": int(q.get("consumers") or 0),
        "publish_rate": float(publish_details.get("rate") or 0.0),
        "deliver_rate": float(deliver_details.get("rate") or 0.0),
    }


def _serialize_plugins() -> List[Dict[str, Any]]:
    """Read the in-process liveness registry and add a derived
    ``last_heartbeat_age_seconds`` so the UI can color-code staleness
    without re-parsing timestamps client-side."""
    now = datetime.now(timezone.utc)
    out: List[Dict[str, Any]] = []
    for entry in get_registry().list_live():
        d = entry.to_dict()
        if entry.last_heartbeat is not None:
            d["last_heartbeat_age_seconds"] = (now - entry.last_heartbeat).total_seconds()
        else:
            d["last_heartbeat_age_seconds"] = None
        out.append(d)
    return out


def get_broker_health(settings: RabbitMQSettings) -> Dict[str, Any]:
    """Build the response payload for ``GET /admin/broker/health``.

    Broker-unreachable is a first-class state, not a 5xx — the page
    should still render with the plugin-liveness section + a clear
    "broker unreachable" banner for the pipeline tiles.
    """
    host = settings.HOST_NAME or "localhost"
    port = _mgmt_port()

    broker_block: Dict[str, Any] = {
        "host": host,
        "management_port": port,
        "reachable": False,
        "error": None,
    }
    queues_by_name: Dict[str, Dict[str, Any]] = {}

    try:
        queues = _fetch_queues(settings)
        queues_by_name = {q.get("name"): q for q in queues if q.get("name")}
        broker_block["reachable"] = True
    except HTTPError as exc:
        broker_block["error"] = f"HTTP {exc.code} from management API ({exc.reason})"
        logger.warning("broker health: management API HTTP %s", exc.code)
    except URLError as exc:
        broker_block["error"] = f"cannot reach {host}:{port} ({exc.reason})"
        logger.warning("broker health: management API unreachable: %s", exc.reason)
    except Exception as exc:  # noqa: BLE001 — surface any decode/parse error to UI
        broker_block["error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("broker health: unexpected error")

    pipelines = []
    for p in _PIPELINES:
        task_q_name = getattr(settings, p.task_queue_attr, None)
        result_q_name = getattr(settings, p.result_queue_attr, None)
        pipelines.append({
            "name": p.name,
            "task_queue": _project_queue(task_q_name, queues_by_name),
            "result_queue": _project_queue(result_q_name, queues_by_name),
        })

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "broker": broker_block,
        "pipelines": pipelines,
        "plugins": _serialize_plugins(),
    }


__all__ = ["get_broker_health"]

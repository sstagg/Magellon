import logging
import asyncio
from typing import Any, Optional

import socketio

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Asgi loop capture — needed by sync callers (RMQ result consumer, dispatch
# audit) that want to emit Socket.IO events. Set once at startup.
# ---------------------------------------------------------------------------

_asgi_loop: Optional[asyncio.AbstractEventLoop] = None


def set_asgi_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Capture the asgi event loop so :func:`schedule_test_envelope` and
    similar sync wrappers can dispatch coroutines via
    ``run_coroutine_threadsafe``. Called from the FastAPI startup hook."""
    global _asgi_loop
    _asgi_loop = loop


def get_asgi_loop() -> Optional[asyncio.AbstractEventLoop]:
    return _asgi_loop

# Create the Socket.IO async server
# Using in-memory adapter (sufficient for < 100 users)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    await sio.emit('server_message', {'message': 'Welcome! You are connected.'}, room=sid)


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


# --- Test endpoints ---

@sio.event
async def ping(sid, data):
    """Simple ping/pong to verify the connection works."""
    logger.info(f"Ping from {sid}: {data}")
    await sio.emit('pong', {'echo': data, 'from': 'server'}, room=sid)


async def _run_job_simulation(sid, job_name, total_steps):
    """Background coroutine that pushes progress updates to the client."""
    try:
        for step in range(1, total_steps + 1):
            await asyncio.sleep(1)  # simulate work
            progress = {
                'job_name': job_name,
                'step': step,
                'total_steps': total_steps,
                'percent': round(step / total_steps * 100),
                'status': 'running',
            }
            await sio.emit('job_progress', progress, room=sid)

        await sio.emit('job_progress', {
            'job_name': job_name,
            'step': total_steps,
            'total_steps': total_steps,
            'percent': 100,
            'status': 'completed',
        }, room=sid)

        logger.info(f"Job simulation '{job_name}' completed for {sid}")
    except Exception as exc:
        logger.warning(f"Job simulation '{job_name}' aborted for {sid}: {exc}")


@sio.event
async def start_job_simulation(sid, data):
    """
    Simulates a long-running job that pushes progress updates to the client.
    Spawns as a background task so the handler returns immediately
    and progress emits flow to the client in real time.
    """
    job_name = data.get('job_name', 'test-job') if data else 'test-job'
    total_steps = data.get('total_steps', 10) if data else 10
    logger.info(f"Starting job simulation '{job_name}' for {sid} ({total_steps} steps)")
    sio.start_background_task(_run_job_simulation, sid, job_name, total_steps)


@sio.event
async def broadcast_message(sid, data):
    """Send a message to ALL connected clients (including sender)."""
    message = data.get('message', '') if data else ''
    logger.info(f"Broadcast from {sid}: {message}")
    await sio.emit('server_broadcast', {'from_sid': sid, 'message': message})


# ---------------------------------------------------------------------------
# Log streaming — emits to all connected clients
# ---------------------------------------------------------------------------

async def emit_log(level: str, source: str, message: str):
    """Broadcast a log entry to all connected clients."""
    import datetime
    entry = {
        'id': f"log-{datetime.datetime.now().timestamp()}",
        'timestamp': datetime.datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'source': source,
        'message': message,
    }
    try:
        await sio.emit('log_entry', entry)
    except Exception:
        pass  # no clients connected


# ---------------------------------------------------------------------------
# Job progress — particle picking and other real jobs
# ---------------------------------------------------------------------------

async def emit_job_update(sid: str | None, job_data: dict):
    """
    Push a job status update. If sid is given, unicast; otherwise broadcast.
    """
    try:
        if sid:
            await sio.emit('job_update', job_data, room=sid)
        else:
            await sio.emit('job_update', job_data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Step events — per-job room subscriptions so the UI sees live plugin
# lifecycle + progress without polling. Room naming: "job:<uuid>".
# ---------------------------------------------------------------------------


def _job_room(job_id) -> str:
    return f"job:{job_id}"


@sio.event
async def join_job_room(sid, data):
    """Client opts into a specific job's event stream.

    Payload: ``{"job_id": "<uuid>"}``. Idempotent — re-joining the same
    room is a no-op.

    After joining, replays persisted lifecycle events (started /
    completed / failed) for the job to *this sid only*. Closes the
    race where a fast plugin finishes before the UI mounts and joins.
    Progress events are not persisted so they can't be replayed; the
    client dedupes on CloudEvents ``id`` so any overlap with live
    delivery collapses cleanly.
    """
    job_id = (data or {}).get("job_id")
    if not job_id:
        return {"ok": False, "error": "job_id required"}
    await sio.enter_room(sid, _job_room(job_id))
    logger.info(f"sid={sid} joined {_job_room(job_id)}")
    await _replay_persisted_events(sid, job_id)
    return {"ok": True, "room": _job_room(job_id)}


async def _replay_persisted_events(sid: str, job_id: str) -> None:
    """Re-emit persisted lifecycle events for ``job_id`` to ``sid``.

    Queries ``job_event`` ordered by ``ts`` and emits each row in the
    same shape :func:`emit_step_event` produces, so the React client
    sees no difference between replayed and live deliveries.
    """
    rows = await asyncio.to_thread(_load_persisted_events, job_id)
    for payload in rows:
        try:
            await sio.emit("step_event", payload, room=sid)
        except Exception:
            logger.exception("replay emit failed for sid=%s event_id=%s", sid, payload.get("id"))
    if rows:
        logger.info("replayed %d persisted event(s) to sid=%s for job=%s", len(rows), sid, job_id)


def _load_persisted_events(job_id: str) -> list[dict]:
    from database import session_local
    from models.sqlalchemy_models import JobEvent

    db = session_local()
    try:
        rows = (
            db.query(JobEvent)
            .filter(JobEvent.job_id == job_id)
            .order_by(JobEvent.ts.asc())
            .all()
        )
        return [
            {
                "id": r.event_id,
                "type": r.event_type,
                "source": r.source,
                "subject": f"magellon.job.{r.job_id}.step.{r.step}",
                "time": r.ts.isoformat() if r.ts else None,
                "data": r.data_json or {},
            }
            for r in rows
        ]
    finally:
        db.close()


@sio.event
async def leave_job_room(sid, data):
    job_id = (data or {}).get("job_id")
    if not job_id:
        return {"ok": False, "error": "job_id required"}
    await sio.leave_room(sid, _job_room(job_id))
    logger.info(f"sid={sid} left {_job_room(job_id)}")
    return {"ok": True}


async def emit_step_event(envelope) -> None:
    """Broadcast a step-event envelope to its job room.

    ``envelope`` is a :class:`magellon_sdk.envelope.Envelope`. We emit
    the CloudEvents-shaped payload as-is so the frontend reads the same
    shape it would off NATS/RMQ — one canonical event model across all
    transports.
    """
    data = envelope.data if isinstance(envelope.data, dict) else {}
    job_id = data.get("job_id")
    if not job_id:
        return
    payload = {
        "id": envelope.id,
        "type": envelope.type,
        "source": envelope.source,
        "subject": envelope.subject,
        "time": envelope.time.isoformat() if envelope.time else None,
        "data": data,
    }
    try:
        await sio.emit("step_event", payload, room=_job_room(job_id))
    except Exception:
        logger.exception("emit_step_event failed (non-fatal)")


# ---------------------------------------------------------------------------
# Plugin test envelope — live tap of bus traffic for the test panel.
# Emits both outgoing TaskMessage and incoming TaskResultMessage onto
# the job room so the React side sees the wire shapes in real time.
# Step events still flow through ``step_event`` independently.
# ---------------------------------------------------------------------------


async def emit_test_envelope(
    direction: str,
    kind: str,
    job_id: Optional[str],
    payload: Any,
    *,
    transport: str = "bus",
    queue: Optional[str] = None,
) -> None:
    """Emit one test-envelope frame to ``job:{job_id}`` room.

    ``direction``: ``"out"`` (CoreService → plugin) or ``"in"``
    (plugin → CoreService).
    ``kind``: ``"task"`` for outgoing dispatch; ``"result"`` for
    incoming results. The React panel renders task vs result with
    different framing.
    ``job_id``: filters which clients see it. Without a job id we
    cannot route, so we drop silently — production traffic is always
    keyed to a job.
    ``payload``: the wire-shape dict (already ``model_dump(mode='json')``).
    ``transport``: ``"bus"`` (RMQ) or ``"sync"`` (HTTP). Sync envelopes
    are normally rendered client-side from the HTTP response, but a
    shared shape lets us mix them in the same panel if we ever want to.
    ``queue``: optional queue name for the audit row's debug context.
    """
    if not job_id:
        return
    frame = {
        "direction": direction,
        "kind": kind,
        "transport": transport,
        "queue": queue,
        "payload": payload,
    }
    try:
        await sio.emit("plugin_test_envelope", frame, room=_job_room(str(job_id)))
    except Exception:
        logger.exception("emit_test_envelope failed (non-fatal)")


def schedule_test_envelope(
    direction: str,
    kind: str,
    job_id: Optional[str],
    payload: Any,
    *,
    transport: str = "bus",
    queue: Optional[str] = None,
) -> None:
    """Sync wrapper — schedule :func:`emit_test_envelope` onto the
    captured asgi loop. Safe to call from any thread, no-ops cleanly
    when the loop hasn't been captured (early boot, tests).
    """
    if _asgi_loop is None:
        return
    coro = emit_test_envelope(
        direction, kind, job_id, payload,
        transport=transport, queue=queue,
    )
    try:
        asyncio.run_coroutine_threadsafe(coro, _asgi_loop)
    except Exception:
        logger.debug("schedule_test_envelope: scheduling failed", exc_info=True)

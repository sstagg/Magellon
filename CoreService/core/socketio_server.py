import logging
import asyncio
import socketio

logger = logging.getLogger(__name__)

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

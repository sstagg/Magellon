"""Import progress events, from wherever an import runs to the browser.

Imports run in separate import-worker processes, but the browsers' live
progress comes through the web backend's Socket.IO server. ``publish`` works
in both places:

* in the web backend (its event loop is captured) → emit directly;
* in an import worker → publish on a Dragonfly (Redis) channel, which
  ``start_relay`` (run once by the backend at startup) forwards to Socket.IO.

Progress is best-effort: if the channel is down, imports carry on and the
import dialog still advances through its regular summary polling.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

CHANNEL = "magellon:import_progress"
_client = None
_client_lock = threading.Lock()


def _connect(socket_timeout):
    import redis
    return redis.Redis(
        host=os.environ.get("DRAGONFLY_HOST", "dragonfly"),
        port=int(os.environ.get("DRAGONFLY_PORT", "6379")),
        password=os.environ.get("DRAGONFLY_PASSWORD") or None,
        socket_connect_timeout=5,
        socket_timeout=socket_timeout,
    )


def _redis():
    """Shared publishing client: short timeouts so a down channel never stalls an import."""
    global _client
    with _client_lock:
        if _client is None:
            _client = _connect(socket_timeout=5)
        return _client


def publish(job_id, data: dict) -> None:
    """Send one ``import_progress`` event for ``job_id`` to its browsers."""
    from core.socketio_server import get_asgi_loop, schedule_import_progress

    if get_asgi_loop() is not None:
        schedule_import_progress(str(job_id), data)
        return
    try:
        _redis().publish(CHANNEL, json.dumps({"job_id": str(job_id), "data": data}, default=str))
    except Exception:
        logger.debug("import progress publish failed", exc_info=True)


def start_relay() -> None:
    """Forward events published by import workers to Socket.IO (backend only)."""
    def run():
        from core.socketio_server import schedule_import_progress
        while True:
            try:
                # Own connection, no read timeout: a subscription sits idle
                # whenever no import is running.
                pubsub = _connect(socket_timeout=None).pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(CHANNEL)
                logger.info("Import progress relay listening on %s", CHANNEL)
                for message in pubsub.listen():
                    try:
                        event = json.loads(message["data"])
                        schedule_import_progress(event["job_id"], event["data"])
                    except Exception:
                        logger.debug("bad import progress message", exc_info=True)
            except Exception:
                logger.warning("Import progress relay disconnected; retrying in 5s", exc_info=True)
                time.sleep(5)

    threading.Thread(target=run, name="import-progress-relay", daemon=True).start()

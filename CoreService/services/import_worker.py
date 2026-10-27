"""Import worker: runs queued imports outside the web backend.

Run as its own container (``python -m services.import_worker``, same image
as the backend). Each worker process runs up to
``MAGELLON_MAX_CONCURRENT_IMPORTS`` imports at once, taking them from the
durable queue in fair order (services/import_queue.py). Several workers —
on this host or others sharing the database and storage — can run side by
side; the queue's atomic claim keeps them from running the same import.

Each import runs in its own child process, so Stop (services/import_queue
``request_stop``) can end one import at once — even halfway through reading
its session — without disturbing the others.

While an import runs the worker heartbeats every 30 s. If a worker dies
without warning, any surviving or restarted worker notices the stale
heartbeat and marks that import failed. On a normal stop (SIGTERM, e.g. a
deploy) the worker stops taking new imports and marks the ones it was
running failed straight away, so users don't wait for the timeout.

The web backend keeps serving pages, results and live progress (relayed
from here through Dragonfly) regardless of how busy the workers are.
"""
import logging
import multiprocessing
import os
import signal
import socket
import sys
import threading
from types import SimpleNamespace

from services import import_queue, import_runners

logger = logging.getLogger("import_worker")

POLL_SECONDS = 2
MAINTENANCE_SECONDS = 60

_stop = threading.Event()
_running = set()
_running_lock = threading.Lock()
_children = {}  # import id → its child process
# How often a running import checks whether the user pressed Stop.
STOP_POLL_SECONDS = 2
_mp = multiprocessing.get_context("spawn")


def _setup_process() -> None:
    """Process-wide setup the importers depend on: the message bus (CTF /
    MotionCor dispatch) and the session-owner hook."""
    from core.dispatcher_registry import install_core_bus
    install_core_bus()
    import core.session_ownership  # noqa: F401  (registers the owner stamp)


def _child(row: dict, conn) -> None:
    """Child process: run one import; send back its error (None = success)."""
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    error = None
    try:
        _setup_process()
        import_runners.run(SimpleNamespace(**row))
    except Exception as exc:
        logging.getLogger("import_worker").exception("Import %s raised", row["id"])
        error = f"{type(exc).__name__}: {exc}"
    conn.send(error)
    conn.close()


def _run_in_child(row) -> tuple:
    """Run the import in a child process; returns (error, stopped)."""
    parent_conn, child_conn = _mp.Pipe(duplex=False)
    data = {"id": row.id, "kind": row.kind, "label": row.label, "payload": row.payload, "owner_id": row.owner_id}
    proc = _mp.Process(target=_child, args=(data, child_conn), name=f"import-{row.id[:8]}", daemon=True)
    proc.start()
    child_conn.close()
    with _running_lock:
        _children[row.id] = proc
    try:
        while proc.is_alive():
            proc.join(STOP_POLL_SECONDS)
            if not proc.is_alive():
                break
            current = import_queue.get(row.id)
            if current is not None and current.status == import_queue.STOPPING:
                logger.warning("Stop requested for import %s: ending it", row.id)
                proc.terminate()
                proc.join(10)
                if proc.is_alive():
                    proc.kill()
                    proc.join()
                return None, True
        error = parent_conn.recv() if parent_conn.poll() else (
            f"The import process ended unexpectedly (exit code {proc.exitcode}).")
        return error, False
    finally:
        parent_conn.close()
        with _running_lock:
            _children.pop(row.id, None)


def _heartbeat(job_id: str, done: threading.Event) -> None:
    while not done.wait(import_queue.HEARTBEAT_SECONDS):
        try:
            import_queue.heartbeat(job_id)
        except Exception:
            logger.warning("heartbeat failed for %s", job_id, exc_info=True)


def _run(row) -> None:
    logger.info("Starting import %s (%s: %s, owner %s)", row.id, row.kind, row.label, row.owner_id)
    with _running_lock:
        _running.add(row.id)
    done = threading.Event()
    threading.Thread(target=_heartbeat, args=(row.id, done), daemon=True).start()
    error, stopped = None, False
    try:
        error, stopped = _run_in_child(row)
    except Exception as exc:
        logger.exception("Import %s raised", row.id)
        error = f"{type(exc).__name__}: {exc}"
    finally:
        done.set()
        with _running_lock:
            _running.discard(row.id)
        if stopped:
            # The backend that asked for the stop removes what the import
            # created and marks it cancelled; just record it ended.
            import_queue.mark_stopped(row.id)
            import_runners.cleanup(row.id)
            logger.warning("Stopped import %s", row.id)
        elif not _stop.is_set():
            import_queue.finish(row.id, error)
            logger.info("Finished import %s%s", row.id, f" with error: {error}" if error else "")


def _slot(name: str) -> None:
    while not _stop.is_set():
        try:
            row = import_queue.claim_next(name)
        except Exception:
            logger.exception("Could not claim from the import queue; retrying")
            _stop.wait(POLL_SECONDS * 5)
            continue
        if row is None:
            _stop.wait(POLL_SECONDS)
            continue
        _run(row)


def _maintenance() -> None:
    from services import jobs_cleanup, stale_jobs

    while not _stop.wait(MAINTENANCE_SECONDS):
        try:
            import_queue.recover_stale()
        except Exception:
            logger.warning("stale-import recovery failed", exc_info=True)
        try:
            stale_jobs.fail_stale_queued()
        except Exception:
            logger.warning("stale plugin-job check failed", exc_info=True)
        # Nightly removal of finished scratch folders in the jobs directory.
        jobs_cleanup.run_if_due()


def _shutdown(signum, _frame) -> None:
    if _stop.is_set():
        return
    _stop.set()
    with _running_lock:
        running = list(_running)
    logger.warning("Stopping (signal %s): no new imports; %d running import(s) will be marked failed",
                   signum, len(running))
    with _running_lock:
        children = list(_children.values())
    for proc in children:
        proc.kill()
    if running:
        try:
            import_queue.fail_running(
                running, "The import worker was restarted while this import was running; please import again.")
        except Exception:
            logger.exception("Could not mark running imports failed; stale recovery will")
    # Running import threads can't be safely interrupted mid-step; exit now
    # and let the container stop.
    os._exit(0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


    name = f"{socket.gethostname()}:{os.getpid()}"
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    import_queue.recover_stale()
    stats = import_queue.stats()
    logger.info("Import worker %s ready: %d slot(s); queue: %d waiting, %d running elsewhere",
                name, import_queue.MAX_CONCURRENT_IMPORTS, stats["waiting"], stats["running"])

    threading.Thread(target=_maintenance, name="maintenance", daemon=True).start()
    slots = [threading.Thread(target=_slot, args=(f"{name}/{i}",), name=f"slot-{i}", daemon=True)
             for i in range(import_queue.MAX_CONCURRENT_IMPORTS)]
    for slot in slots:
        slot.start()
    _stop.wait()


if __name__ == "__main__":
    main()

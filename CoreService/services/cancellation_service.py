"""Plugin / job cancellation primitives (P9 + MB6.1).

Two operations, paired because together they cover the realistic
cancel-everything story:

  - :func:`purge_queue` — drain pending tasks for a category. The
    broker has no notion of "cancel by job-id", so we purge the whole
    in-flight queue. That's intentional: by the time an operator hits
    cancel, the cheaper move is to throw away pending work and let the
    plugin re-enqueue if it wants to.

  - :func:`kill_plugin_container` — stop a plugin instance that's
    mid-execute. Queue purge alone won't help here because the in-
    flight delivery is already in the plugin's hands. ``docker kill``
    is the only universal "stop now" hammer for a long-running
    motioncor / ctf job.

Both are deliberately thin around the underlying client so the FastAPI
controller can stay an authz + log layer with no broker / docker
imports of its own.

Post-MB6.1: :func:`purge_queue` delegates to the installed MessageBus
(``bus.tasks.purge``). The pika connection, channel lifecycle, and
passive-declare safety check are all the binder's responsibility.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.routes import TaskRoute

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue purge
# ---------------------------------------------------------------------------

def purge_queue(rabbitmq_settings: Any, queue_name: str) -> int:
    """Drop every pending message from ``queue_name``.

    Returns the count purged so callers can log "cancelled N tasks".

    Delegates to ``bus.tasks.purge`` — the binder handles the
    connection, the passive-declare safety check ("fail if the queue
    doesn't exist" so typo'd cancels don't silently succeed), and the
    purge itself.

    The ``rabbitmq_settings`` argument is retained for backwards
    compatibility with the FastAPI controller; it is no longer
    consulted — the bus was already configured at startup from the
    same settings. Future PR can drop the argument once callers no
    longer pass it.
    """
    count = get_bus().tasks.purge(TaskRoute.named(queue_name))
    logger.info("purge_queue: %s → %d message(s) discarded", queue_name, count)
    return count


def purge_queues(rabbitmq_settings: Any, queue_names: List[str]) -> Dict[str, int]:
    """Purge several queues in one operator action.

    Returns ``{queue_name: count_purged}`` — partial success is fine
    (one missing queue must not block the others), so individual
    failures are caught and recorded as ``-1`` rather than raised.
    A real failure (e.g., bus unreachable) still propagates from the
    first call, which is what we want.
    """
    out: Dict[str, int] = {}
    for q in queue_names:
        try:
            out[q] = purge_queue(rabbitmq_settings, q)
        except Exception as exc:
            logger.warning("purge_queues: %s failed: %s", q, exc)
            out[q] = -1
    return out


# ---------------------------------------------------------------------------
# Container kill
# ---------------------------------------------------------------------------

def kill_plugin_container(
    container_name: str,
    *,
    docker_url: Optional[str] = None,
    signal: str = "SIGKILL",
) -> Dict[str, Any]:
    """``docker kill`` the named plugin container.

    Plugin replicas are addressable by container name (set in
    docker-compose) — we don't keep a registry of container ids
    because the live-plugin registry from P6 carries instance ids,
    which are *process* identifiers, not container identifiers.
    Matching the two would mean asking each plugin to publish its
    container id, which is awkward inside Docker. Operator passes
    the container name explicitly instead.

    Returns a small dict the controller can echo back. Errors from
    the docker daemon (container not found, daemon unreachable) are
    re-raised so the controller turns them into 4xx / 5xx — silently
    succeeding here would be the worst possible outcome for an
    operator hitting "cancel".
    """
    # Imported lazily so the cancellation API doesn't require the
    # docker package to be installed for unit tests.
    import docker

    client = docker.DockerClient(base_url=docker_url) if docker_url else docker.from_env()
    try:
        container = client.containers.get(container_name)
        container.kill(signal=signal)
        logger.info("kill_plugin_container: %s killed (signal=%s)", container_name, signal)
        return {
            "container_name": container_name,
            "id": container.id,
            "signal": signal,
            "status": "killed",
        }
    finally:
        try:
            client.close()
        except Exception:
            pass


__all__ = [
    "kill_plugin_container",
    "purge_queue",
    "purge_queues",
]

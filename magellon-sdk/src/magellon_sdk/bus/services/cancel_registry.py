"""Process-wide cancel registry + bus listener (G.1).

Cooperative cancel for external plugins. The plan:

- CoreService publishes ``magellon.plugins.cancel.<job_id>`` on the
  bus when an operator cancels a job (or when
  ``JobManager.request_cancel`` fires for any other reason).
- Every plugin process has a :class:`PluginBrokerRunner` which
  subscribes to :func:`CancelRoute.all` and marks cancelled job_ids
  in this module's process-wide :class:`CancelRegistry`.
- Plugin code at each progress checkpoint (``reporter.progress(...)``
  in ``BoundStepReporter``) reads the registry and raises
  :class:`JobCancelledError` if its job was marked. The runner
  catches the raise and publishes a failure-status result so the
  user's task row flips out of RUNNING.

Registry is intentionally in-memory + non-persistent: a plugin
process restart drops the set, but the cancel event republishes
as soon as the operator re-issues it, or falls away if the job has
already finished.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional, Set
from uuid import UUID

from pydantic import BaseModel

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus, SubscriptionHandle
from magellon_sdk.bus.routes.event_route import CancelRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

logger = logging.getLogger(__name__)


class CancelMessage(BaseModel):
    """Wire shape carried by :class:`CancelRoute.for_job`.

    ``job_id`` drives the subject routing key AND is mirrored in the
    body so a subscriber bound on a wildcard pattern doesn't have to
    parse the subject. ``requested_by`` / ``reason`` are for audit
    trails only — no plugin behavior depends on them.
    """

    job_id: UUID
    requested_by: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CancelRegistry:
    """Thread-safe set of cancelled job_ids.

    Small on purpose — all operations are O(1) hashset work under a
    single lock. The set is never truly pruned: a cancelled job stays
    cancelled for the life of the process. Plugin restarts flush the
    set, which is fine (if the job is still live when the plugin
    restarts, it'll receive another cancel pulse on reconnect).
    """

    def __init__(self) -> None:
        self._cancelled: Set[str] = set()
        self._lock = threading.Lock()

    def mark_cancelled(self, job_id: UUID | str) -> None:
        key = str(job_id)
        with self._lock:
            self._cancelled.add(key)

    def is_cancelled(self, job_id: UUID | str | None) -> bool:
        if job_id is None:
            return False
        with self._lock:
            return str(job_id) in self._cancelled

    def clear(self, job_id: UUID | str) -> None:
        key = str(job_id)
        with self._lock:
            self._cancelled.discard(key)

    def snapshot(self) -> Set[str]:
        """Read-only copy — tests + diagnostics."""
        with self._lock:
            return set(self._cancelled)

    def reset(self) -> None:
        """Test-only: drop every entry."""
        with self._lock:
            self._cancelled.clear()


# Process-wide singleton — matches the pattern of every other bus
# service in this package (liveness_registry, config_publisher).
_REGISTRY: Optional[CancelRegistry] = None


def get_cancel_registry() -> CancelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CancelRegistry()
    return _REGISTRY


# ---------------------------------------------------------------------------
# Bus listener
# ---------------------------------------------------------------------------

class CancelListener:
    """Holder for the bus subscription feeding the cancel registry.

    Matches :class:`LivenessListener`'s shape so callers have a
    consistent ``.stop()`` affordance on shutdown.
    """

    def __init__(
        self,
        *,
        registry: CancelRegistry,
        handle: SubscriptionHandle,
    ) -> None:
        self.registry = registry
        self._handle = handle

    def stop(self) -> None:
        try:
            self._handle.close()
        except Exception:  # noqa: BLE001 — shutdown best-effort
            logger.exception("cancel listener: handle close failed")


def start_cancel_listener(
    *,
    registry: Optional[CancelRegistry] = None,
    bus: Optional[MessageBus] = None,
) -> CancelListener:
    """Subscribe to :func:`CancelRoute.all` and mark each cancelled job_id.

    The handler decodes each delivery's :class:`Envelope` into a
    :class:`CancelMessage` and calls ``registry.mark_cancelled``.
    Malformed payloads raise :class:`PermanentError` so the binder
    routes them to the DLQ instead of redelivering.
    """
    target = registry or get_cancel_registry()
    resolved_bus = bus if bus is not None else get_bus()

    def _on_cancel(envelope: Envelope) -> None:
        try:
            msg = CancelMessage.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"cancel listener: bad CancelMessage payload: {exc}") from exc
        target.mark_cancelled(msg.job_id)
        logger.info(
            "cancel listener: marked job_id=%s cancelled (requested_by=%s reason=%s)",
            msg.job_id, msg.requested_by, msg.reason,
        )

    handle = resolved_bus.events.subscribe(CancelRoute.all(), _on_cancel)
    logger.info("cancel listener: subscribed to magellon.plugins.cancel.>")

    return CancelListener(registry=target, handle=handle)


__all__ = [
    "CancelListener",
    "CancelMessage",
    "CancelRegistry",
    "get_cancel_registry",
    "start_cancel_listener",
]

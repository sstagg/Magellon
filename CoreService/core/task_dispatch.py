"""The single task-dispatch chokepoint: ``push_task_to_task_queue``.

Every importer + detection/picking dispatch helper flows through this
module. It stamps the subject axis, writes the on-disk audit line,
emits the test-panel envelope tap, then hands the task to the
dispatcher registry.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
import logging
import os
import uuid

from core.exceptions import TaskDispatchError
from core.file_utils import append_json_to_file
from core.queue_names import get_queue_name_by_task_type
from magellon_sdk.models import TaskMessage

logger = logging.getLogger(__name__)


def push_task_to_task_queue(task: TaskMessage) -> bool:
    """Push a task to its worker via the configured dispatcher.

    Delegates to :class:`magellon_sdk.dispatcher.TaskDispatcherRegistry`;
    adding a new plugin is now a single ``registry.register(...)`` call
    in :mod:`core.dispatcher_registry` — no edit to this function or
    the task-type→queue switch needed.

    Returns the dispatcher's receipt boolean (``False`` means the bus
    accepted the call but reported a not-ok publish receipt — the
    legacy ``publish_message_to_queue`` contract).

    Raises:
        TaskDispatchError: when the dispatch pipeline itself fails
            (broker outage, misconfigured registry, ``BackendNotLive``,
            ...). Previously this degraded to ``return False``, which
            callers that ignored the boolean silently lost; now the
            failure propagates so unhandled cases surface as 500s.
    """
    try:
        from core.dispatcher_registry import get_task_dispatcher_registry

        _stamp_image_subject(task)
        _audit_outgoing_message(task)
        _emit_outgoing_envelope(task)
        return get_task_dispatcher_registry().dispatch(task)
    except Exception as e:
        logger.exception("Error pushing task %s (type=%s) to queue", task.id, task.type)
        raise TaskDispatchError(
            f"failed to dispatch task {task.id} ({task.type}): {e}"
        ) from e


def _stamp_image_subject(task: TaskMessage) -> None:
    """Stamp the image subject axis on a task at the dispatch boundary.

    Phase 3 / A.2: dispatch is the *authoritative* writer of
    ``subject_kind`` / ``subject_id``. Every task built by the
    importers and the detection/picking dispatch helpers is image-keyed,
    so when the caller hasn't already set a richer subject (e.g. a
    ``particle_stack`` for 2D classification), we derive ``'image'`` +
    the payload's ``image_id`` here. The runner's ``_stamp_subject``
    contract default and the projector's Phase-3c backfill remain only
    as fallbacks for tasks that never pass through this boundary.

    No-op when the caller already set ``subject_kind`` or the payload
    carries no ``image_id``.
    """
    if task.subject_kind is not None:
        return
    data = task.data
    if data is None:
        return
    if isinstance(data, dict):
        image_id = data.get("image_id")
    else:
        image_id = getattr(data, "image_id", None)
    if image_id in (None, ""):
        return
    task.subject_kind = "image"
    if isinstance(image_id, uuid.UUID):
        task.subject_id = image_id
    else:
        try:
            task.subject_id = uuid.UUID(str(image_id))
        except (ValueError, TypeError):
            # Keep subject_kind='image' even if the id is unparseable —
            # the kind alone still routes correctly; subject_id stays None.
            logger.debug("could not parse image_id %r as UUID for subject_id", image_id)


def _emit_outgoing_envelope(task: TaskMessage) -> None:
    """Live tap for the test panel — emits the dispatched TaskMessage to
    its job's Socket.IO room. Same shape the React side renders for
    incoming results, so the panel sees both halves of the round-trip.
    Best-effort — never blocks dispatch.
    """
    try:
        from core.socketio_server import schedule_test_envelope
        queue_name = get_queue_name_by_task_type(task.type, is_result=False)
        schedule_test_envelope(
            "out", "task",
            str(task.job_id) if task.job_id else None,
            task.model_dump(mode="json"),
            transport="bus",
            queue=queue_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("envelope tap (out) failed (non-fatal): %s", exc)


def _audit_outgoing_message(task: TaskMessage) -> None:
    """Best-effort on-disk audit log of outgoing tasks.

    Writes one JSON line per dispatched task to
    ``/magellon/messages/<queue>/messages.json``. Matches the old
    ``publish_message_to_queue`` behaviour so operators keep their
    audit trail through the dispatcher migration. Failures are
    swallowed — this is diagnostics, not correctness.
    """
    try:
        queue_name = get_queue_name_by_task_type(task.type, is_result=False)
        if not queue_name:
            return
        destination_dir = os.path.join("/magellon", "messages", queue_name)
        os.makedirs(destination_dir, exist_ok=True)
        append_json_to_file(
            os.path.join(destination_dir, "messages.json"),
            task.model_dump_json(),
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("outgoing-message audit failed (non-fatal): %s", e)

"""Work-queue routes.

``TaskRoute`` names the *incoming* side of a category (where tasks are
dispatched to); ``TaskResultRoute`` names the *outgoing* side (where
plugins publish their ``TaskResultMessage``).

Both delegate to ``CategoryContract`` for the subject string — the
contract is the single source of truth for subject naming (see
``Documentation/MESSAGE_BUS_SPEC_AND_PLAN.md`` §1.3, §4.3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.categories.contract import CategoryContract


@dataclass(frozen=True)
class TaskRoute:
    """Where a task is dispatched to.

    ``subject`` is the source of truth for observability — every binder
    uses it for the CloudEvents ``ce-subject`` header, the audit log,
    and any operator-facing log line.

    ``physical_queue`` is an optional binder-level override (X.1+). When
    set, the binder publishes to that queue instead of resolving
    ``subject`` through ``legacy_queue_map``. This is how backend-pinned
    dispatch works: the dispatcher knows the destination queue from
    the liveness registry's per-plugin ``Announce.task_queue`` and
    passes it through here, while ``subject`` stays symbolic
    (``magellon.tasks.<category>.<backend>``) for logs.
    """

    subject: str
    physical_queue: Optional[str] = None

    @classmethod
    def for_category(cls, contract: CategoryContract) -> "TaskRoute":
        """Canonical route for a category, read from the contract."""
        return cls(subject=contract.task_subject)

    @classmethod
    def for_backend(
        cls, contract: CategoryContract, backend_id: str, queue: str,
    ) -> "TaskRoute":
        """Backend-pinned route (X.1+).

        Subject is the symbolic ``magellon.tasks.<category>.<backend>``;
        ``queue`` is the physical queue the resolver returned from the
        liveness registry. The binder publishes to ``queue`` directly,
        bypassing ``legacy_queue_map`` resolution. ``subject`` stays
        symbolic so the audit log + ce-subject header carry the
        backend-pin signal an operator can grep.
        """
        return cls(
            subject=contract.task_subject_for_backend(backend_id),
            physical_queue=queue,
        )

    @classmethod
    def named(cls, subject: str) -> "TaskRoute":
        """Explicit escape hatch for non-contract routes (test queues,
        integration harnesses). Prefer :meth:`for_category` for
        production code."""
        return cls(subject=subject)


@dataclass(frozen=True)
class TaskResultRoute:
    """Where a plugin publishes its ``TaskResultMessage``."""

    subject: str

    @classmethod
    def for_category(cls, contract: CategoryContract) -> "TaskResultRoute":
        return cls(subject=contract.result_subject)

    @classmethod
    def named(cls, subject: str) -> "TaskResultRoute":
        return cls(subject=subject)

    @classmethod
    def all(cls) -> EventPattern:
        """Pattern for the result fan-in consumer (CoreService's
        ``TaskOutputProcessor``). Matches every category's result
        subject: ``magellon.tasks.*.result``."""
        return EventPattern(subject_glob="magellon.tasks.*.result")


__all__ = ["TaskResultRoute", "TaskRoute"]

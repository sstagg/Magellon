"""Work-queue routes.

``TaskRoute`` names the *incoming* side of a category (where tasks are
dispatched to); ``TaskResultRoute`` names the *outgoing* side (where
plugins publish their ``TaskResultDto``).

Both delegate to ``CategoryContract`` for the subject string — the
contract is the single source of truth for subject naming (see
``Documentation/MESSAGE_BUS_SPEC_AND_PLAN.md`` §1.3, §4.3).
"""
from __future__ import annotations

from dataclasses import dataclass

from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.categories.contract import CategoryContract


@dataclass(frozen=True)
class TaskRoute:
    """Where a task is dispatched to.

    ``subject`` is the source of truth — every binder translates it to
    its native form (RMQ routing key, NATS subject, etc.).
    """

    subject: str

    @classmethod
    def for_category(cls, contract: CategoryContract) -> "TaskRoute":
        """Canonical route for a category, read from the contract."""
        return cls(subject=contract.task_subject)

    @classmethod
    def named(cls, subject: str) -> "TaskRoute":
        """Explicit escape hatch for non-contract routes (test queues,
        integration harnesses). Prefer :meth:`for_category` for
        production code."""
        return cls(subject=subject)


@dataclass(frozen=True)
class TaskResultRoute:
    """Where a plugin publishes its ``TaskResultDto``."""

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

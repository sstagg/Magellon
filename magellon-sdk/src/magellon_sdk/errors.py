"""Typed failure taxonomy for plugin execution.

Today the broker consumer loops in both CoreService and plugins treat
every exception identically — nack without requeue. That's wrong in
two directions:

  - A transient error (broker blip, temp file missing briefly) ends up
    in the DLQ forever, even though a retry in 30 seconds would have
    succeeded.

  - A poison input (bad MRC, unrecoverable config) gets retried until
    the operator notices, wasting compute and masking the real issue.

This module gives plugins a way to say which they are.

Usage inside a plugin's ``execute()``::

    if not os.path.exists(path):
        # Maybe NFS hiccup — ask the broker to try again later.
        raise RetryableError(
            "input file not yet readable",
            retry_after_seconds=15,
        )

    try:
        parse_mrc(path)
    except MrcFormatError as e:
        # Never going to succeed with this payload. Send to DLQ.
        raise PermanentError(f"invalid MRC header: {e}") from e

The broker harness (P5) and the existing RabbitmqEventConsumer consume
``classify_exception`` to decide ACK / NACK-requeue / NACK-DLQ.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PluginError(Exception):
    """Base class for plugin-signalled failures.

    Generic ``Exception`` subclasses are still fine — they'll be
    treated as "unknown, assume retryable up to a limit" by the
    classifier. Using ``PluginError`` subclasses just lets the plugin
    be explicit instead of leaving the decision to the default policy.
    """


class RetryableError(PluginError):
    """The operation failed *this time* but is expected to succeed on
    retry. Broker requeues with a backoff delay if the transport
    supports it.

    Attributes
    ----------
    retry_after_seconds : optional hint for the broker. ``None`` means
        "use the broker's default backoff". Broker adapters are free
        to clamp this to their supported range.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PermanentError(PluginError):
    """The operation will never succeed for this payload. Broker
    routes the message to the DLQ immediately; no retry."""


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class AckAction(Enum):
    """What the broker consumer should do with a message after the
    callback raised (or returned)."""

    ACK = "ack"
    """Handler succeeded. Remove from queue."""

    REQUEUE = "requeue"
    """Retryable failure. Broker should re-deliver after backoff."""

    DLQ = "dlq"
    """Permanent failure. Broker should route to the dead-letter queue."""


@dataclass(frozen=True)
class Classification:
    """Result of classifying an exception for the broker.

    Kept as a small dataclass (rather than just returning an
    ``AckAction``) so the broker layer can log ``reason`` and
    ``retry_after_seconds`` without re-inspecting the exception.
    """

    action: AckAction
    reason: str
    retry_after_seconds: Optional[float] = None


# Default "retry a few times before giving up" policy — kicks in when a
# plugin raises an untyped exception and we have no other signal. The
# broker layer is expected to track the redelivery count via message
# headers and pass it in; if it doesn't, ``default_max_retries=0``
# means "one attempt, no retry" which is safe (no poison loops).
DEFAULT_MAX_RETRIES = 3


def classify_exception(
    exc: BaseException,
    *,
    redelivery_count: int = 0,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Classification:
    """Decide what to do with a message after ``callback`` raised.

    Rules, in order:

    1. ``PermanentError`` → DLQ immediately, no retry.
    2. ``RetryableError`` → REQUEUE with the plugin's hint (if any).
    3. Any other exception → REQUEUE until ``max_retries`` exhausted,
       then DLQ. This keeps poison messages from looping forever when
       a plugin raises an untyped error.
    """
    if isinstance(exc, PermanentError):
        return Classification(
            action=AckAction.DLQ,
            reason=f"PermanentError: {exc}",
        )

    if isinstance(exc, RetryableError):
        return Classification(
            action=AckAction.REQUEUE,
            reason=f"RetryableError: {exc}",
            retry_after_seconds=exc.retry_after_seconds,
        )

    # Untyped exception — assume recoverable up to the retry ceiling.
    if redelivery_count >= max_retries:
        return Classification(
            action=AckAction.DLQ,
            reason=f"untyped exception after {redelivery_count} retries: {type(exc).__name__}: {exc}",
        )

    return Classification(
        action=AckAction.REQUEUE,
        reason=f"untyped exception, retry {redelivery_count + 1}/{max_retries}: {type(exc).__name__}: {exc}",
    )


__all__ = [
    "AckAction",
    "Classification",
    "DEFAULT_MAX_RETRIES",
    "PermanentError",
    "PluginError",
    "RetryableError",
    "classify_exception",
]

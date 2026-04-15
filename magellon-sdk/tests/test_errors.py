"""Unit tests for the typed failure taxonomy.

The point of these tests is to lock in the routing decisions plugins
rely on: a RetryableError must always be requeued, a PermanentError
must always go to the DLQ, and an untyped exception must not loop
poison messages forever.
"""
from __future__ import annotations

import pytest

from magellon_sdk.errors import (
    AckAction,
    DEFAULT_MAX_RETRIES,
    PermanentError,
    PluginError,
    RetryableError,
    classify_exception,
)


def test_retryable_error_is_plugin_error():
    """Plugins should be able to catch both taxonomy errors with a
    single ``except PluginError`` if they want to introspect."""
    assert isinstance(RetryableError("x"), PluginError)
    assert isinstance(PermanentError("x"), PluginError)


def test_retryable_carries_backoff_hint():
    err = RetryableError("temp file not ready", retry_after_seconds=30)
    assert err.retry_after_seconds == 30
    assert str(err) == "temp file not ready"


def test_retryable_without_hint_has_none():
    err = RetryableError("shrug")
    assert err.retry_after_seconds is None


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

def test_permanent_error_always_goes_to_dlq():
    """Even on a first delivery — that's the point of PermanentError.
    The plugin has told us 'this will never work', so retrying is
    pure waste."""
    c = classify_exception(PermanentError("bad header"), redelivery_count=0)
    assert c.action is AckAction.DLQ
    assert "PermanentError" in c.reason


def test_retryable_error_always_requeues_regardless_of_count():
    """If the plugin raises RetryableError, trust it. Don't decide
    'well you've retried too many times already' — the plugin is
    the authority on whether the error is transient."""
    c = classify_exception(
        RetryableError("NFS blip", retry_after_seconds=15),
        redelivery_count=10,
    )
    assert c.action is AckAction.REQUEUE
    assert c.retry_after_seconds == 15


def test_untyped_exception_requeues_up_to_limit():
    """Give unknown errors the benefit of the doubt, but don't loop
    forever — poison messages hurt."""
    c = classify_exception(RuntimeError("oops"), redelivery_count=0)
    assert c.action is AckAction.REQUEUE

    c = classify_exception(
        RuntimeError("oops"), redelivery_count=DEFAULT_MAX_RETRIES - 1
    )
    assert c.action is AckAction.REQUEUE

    c = classify_exception(
        RuntimeError("oops"), redelivery_count=DEFAULT_MAX_RETRIES
    )
    assert c.action is AckAction.DLQ


def test_untyped_exception_reason_includes_type_name():
    """Logs grep-friendly: operators scanning DLQ reasons should see
    the exception class name, not just a generic 'failed'."""
    c = classify_exception(ValueError("bad shape"), redelivery_count=99)
    assert "ValueError" in c.reason
    assert "bad shape" in c.reason


def test_classification_is_frozen():
    c = classify_exception(RetryableError("x"), redelivery_count=0)
    with pytest.raises(Exception):
        c.action = AckAction.DLQ  # type: ignore[misc]


def test_max_retries_override_works():
    """Long-running plugins may want a more generous ceiling. Keep the
    knob accessible without forcing everyone onto the default."""
    c = classify_exception(
        RuntimeError("flake"), redelivery_count=5, max_retries=10
    )
    assert c.action is AckAction.REQUEUE

    c = classify_exception(
        RuntimeError("flake"), redelivery_count=10, max_retries=10
    )
    assert c.action is AckAction.DLQ

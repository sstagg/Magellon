"""Tests for ``magellon_sdk.bus.services.config_publisher``.

The module is a thin singleton wrapper + two operator-friendly push
helpers. The wrapped :class:`ConfigPublisher` is unit-tested in
``test_config_broker.py``; here we pin the singleton lifecycle and
the helper-function pass-through.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.bus.services.config_publisher import (
    get_config_publisher,
    push_broadcast,
    push_to_category,
    reset_publisher,
)
from magellon_sdk.categories.contract import CTF


@pytest.fixture(autouse=True)
def _reset():
    """The publisher is a process-wide singleton — reset between tests
    so caching from one doesn't leak into the next."""
    reset_publisher()
    yield
    reset_publisher()


def test_get_config_publisher_lazy_constructs_on_first_call():
    """The module shouldn't try to build a publisher at import time
    (would force a broker connection in tests / alembic). First call
    constructs lazily."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        get_config_publisher(MagicMock())
        MockPub.assert_called_once()


def test_get_config_publisher_returns_same_instance_on_subsequent_calls():
    """Singleton contract: every call after the first returns the
    cached publisher. Building one per push would rebuild the bus's
    route value objects every time."""
    with patch("magellon_sdk.bus.services.config_publisher.ConfigPublisher"):
        first = get_config_publisher(MagicMock())
        second = get_config_publisher(MagicMock())
        assert first is second


def test_push_to_category_delegates_to_publisher():
    """Operator-friendly wrapper — should pass arguments through."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        instance = MockPub.return_value
        push_to_category(MagicMock(), CTF, {"max_res": 4.5}, version=7)

        instance.publish_to_category.assert_called_once_with(
            CTF, {"max_res": 4.5}, version=7,
        )


def test_push_broadcast_delegates_to_publisher():
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        instance = MockPub.return_value
        push_broadcast(MagicMock(), {"log_level": "DEBUG"}, version=3)

        instance.publish_broadcast.assert_called_once_with(
            {"log_level": "DEBUG"}, version=3,
        )


def test_push_helpers_share_the_singleton():
    """Two pushes from a single operator session must not rebuild
    the publisher — that would defeat the point of caching it."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        push_to_category(MagicMock(), CTF, {"a": 1})
        push_broadcast(MagicMock(), {"b": 2})

        # ConfigPublisher constructed exactly once across both pushes.
        assert MockPub.call_count == 1


def test_reset_publisher_drops_cached_instance():
    """Test helper — the next get_config_publisher after reset must
    construct a fresh one (otherwise tests sharing state hit each
    other's mocks)."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        get_config_publisher(MagicMock())
        reset_publisher()
        get_config_publisher(MagicMock())
        assert MockPub.call_count == 2


def test_reset_publisher_calls_close_on_existing():
    """When a singleton is dropped, its broker-side resources should
    be released — even though ``close()`` on the new bus-shaped
    publisher is a no-op, the call is still made so any future
    publisher with real cleanup gets it."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        instance = MockPub.return_value
        get_config_publisher(MagicMock())
        reset_publisher()
        instance.close.assert_called_once()


def test_reset_publisher_is_safe_when_no_publisher_cached():
    """Test fixtures and shutdown hooks call reset unconditionally;
    must not raise when the cache is already empty."""
    reset_publisher()  # no exception


def test_reset_publisher_swallows_close_errors():
    """If the cached publisher's close() raises during teardown
    (e.g. broker already gone), we still want the cache cleared so
    the next test doesn't see a half-dead instance."""
    with patch(
        "magellon_sdk.bus.services.config_publisher.ConfigPublisher"
    ) as MockPub:
        instance = MockPub.return_value
        instance.close.side_effect = RuntimeError("broker gone")
        get_config_publisher(MagicMock())

        # Should not raise.
        reset_publisher()

        # Cache cleared: next call constructs fresh.
        get_config_publisher(MagicMock())
        assert MockPub.call_count == 2

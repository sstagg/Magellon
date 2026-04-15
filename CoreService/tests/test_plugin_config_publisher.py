"""Tests for the CoreService config-publisher facade (P7).

The publisher itself is exercised in the SDK's test_config_broker; what
we pin here is the CoreService-side glue:

  - The module-level singleton is reused across calls (so a busy admin
    endpoint isn't re-opening RMQ connections per push).
  - Category vs broadcast helpers route to the right SDK method (i.e.,
    we didn't accidentally swap them).
  - reset_publisher() actually drops the cache — important for tests
    and for any future "rebind on settings change" path.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.categories.contract import CTF
from services import plugin_config_publisher as svc


@pytest.fixture(autouse=True)
def _reset():
    svc.reset_publisher()
    yield
    svc.reset_publisher()


def test_get_config_publisher_returns_singleton():
    """One process = one publisher. Re-creating per call would burn a
    new RMQ connection on every admin click."""
    settings = MagicMock()
    a = svc.get_config_publisher(settings)
    b = svc.get_config_publisher(settings)
    assert a is b


def test_push_to_category_routes_to_sdk_category_method():
    """Sanity: the facade hasn't accidentally swapped the two methods.
    A mis-routed broadcast would push CTF-only knobs onto every plugin."""
    fake_pub = MagicMock()
    with patch.object(svc, "get_config_publisher", return_value=fake_pub):
        svc.push_to_category(MagicMock(), CTF, {"max_res": 4.5}, version=2)

    fake_pub.publish_to_category.assert_called_once_with(CTF, {"max_res": 4.5}, version=2)
    fake_pub.publish_broadcast.assert_not_called()


def test_push_broadcast_routes_to_sdk_broadcast_method():
    fake_pub = MagicMock()
    with patch.object(svc, "get_config_publisher", return_value=fake_pub):
        svc.push_broadcast(MagicMock(), {"log_level": "DEBUG"})

    fake_pub.publish_broadcast.assert_called_once_with({"log_level": "DEBUG"}, version=None)
    fake_pub.publish_to_category.assert_not_called()


def test_reset_publisher_drops_cached_instance():
    """A reset must actually clear the cache — otherwise tests bleed
    into each other and any future settings-rebind path can't take effect."""
    settings = MagicMock()
    first = svc.get_config_publisher(settings)
    svc.reset_publisher()
    second = svc.get_config_publisher(settings)
    assert first is not second

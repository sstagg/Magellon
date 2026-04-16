"""bootstrap.py helper tests.

Thin one-liners: verifies each ``install_*`` wires ``get_bus`` and
each ``build_*`` returns a started bus. Behavior of the underlying
binders is covered by their own test files.
"""
from __future__ import annotations

import pytest

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.binders.mock import MockBinder
from magellon_sdk.bus.bootstrap import (
    build_inmemory_bus,
    build_mock_bus,
    install_inmemory_bus,
    install_mock_bus,
)


@pytest.fixture(autouse=True)
def _reset_bus():
    """Every bootstrap test runs in isolation — no leaked overrides."""
    get_bus.reset()
    yield
    get_bus.reset()


def test_build_inmemory_bus_returns_started_bus_with_inmemory_binder():
    bus = build_inmemory_bus()
    try:
        assert bus._binder.name == "inmemory"  # type: ignore[attr-defined]
        assert isinstance(bus._binder, InMemoryBinder)  # type: ignore[attr-defined]
    finally:
        bus.close()


def test_build_mock_bus_returns_started_bus_with_mock_binder():
    bus = build_mock_bus()
    try:
        assert isinstance(bus._binder, MockBinder)  # type: ignore[attr-defined]
    finally:
        bus.close()


def test_install_inmemory_bus_sets_process_wide_bus():
    bus = install_inmemory_bus()
    try:
        assert get_bus() is bus
    finally:
        bus.close()


def test_install_mock_bus_sets_process_wide_bus():
    bus = install_mock_bus()
    try:
        assert get_bus() is bus
    finally:
        bus.close()


def test_build_rmq_bus_is_importable_without_constructing():
    """Importing build_rmq_bus must not require pika beyond the
    already-installed dependency; constructing it is deferred so
    tests that don't touch RMQ stay fast."""
    from magellon_sdk.bus.bootstrap import build_rmq_bus, install_rmq_bus  # noqa: F401

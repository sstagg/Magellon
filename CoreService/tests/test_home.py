"""Stale ``GET /hello/world`` smoke test.

The endpoint this file targets has been removed — main.py defines
no /hello route. Skipped so the suite is clean; left in place
because tooling on the side regenerates this filename from a
template.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="GET /hello/world endpoint does not exist (stale demo).",
)


def test_say_hello():
    pass

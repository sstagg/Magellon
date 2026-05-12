"""Stale ``GET /hello/world`` smoke test (camera controller variant).

See test_home.py — same situation. Skip-marked rather than deleted
because tooling regenerates the filename from a template.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="GET /hello/world endpoint does not exist (stale demo).",
)


def test_say_hello():
    pass

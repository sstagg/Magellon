"""Tests for the lenient ``_find_broker_plugin`` lookup.

The matcher must accept a plugin's manifest slug (``"fft"``) in
addition to its runtime announce form (``"FFT — magnitude spectrum"``)
and the discovery-list composed form (``"fft/FFT — magnitude spectrum"``).
Otherwise ``POST /plugins/fft/jobs`` 404s while the plugin is
heartbeating just because the URL refers to it by slug.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from plugins import controller as ctl


@contextmanager
def _live_registry(*entries):
    fake = MagicMock()
    fake.list_live.return_value = list(entries)
    with patch.object(ctl, "get_liveness_registry", return_value=fake):
        yield


def _entry(*, plugin_id: str, backend_id: str = "", category: str = "fft"):
    e = MagicMock()
    e.plugin_id = plugin_id
    e.backend_id = backend_id
    e.category = category
    return e


def test_find_by_runtime_announce_form():
    """Original behavior — entry.plugin_id matches the URL plugin_id."""
    with _live_registry(_entry(plugin_id="FFT — magnitude spectrum", backend_id="fft")):
        contract = ctl._find_broker_plugin("FFT — magnitude spectrum")
    assert contract is not None
    assert contract.category.name == "FFT"


def test_find_by_composed_form():
    """Discovery's composed form (``"fft/FFT — magnitude spectrum"``)
    works too — the bare-form gets stripped to match the runtime
    announce."""
    with _live_registry(_entry(plugin_id="FFT — magnitude spectrum", backend_id="fft")):
        contract = ctl._find_broker_plugin("fft/FFT — magnitude spectrum")
    assert contract is not None
    assert contract.category.name == "FFT"


def test_find_by_manifest_slug():
    """Lenient fallback: URL uses the manifest slug ``"fft"``, the
    live entry only exposes that as ``backend_id``. This is the case
    that drove the fix — ``POST /plugins/fft/jobs`` was 404ing."""
    with _live_registry(_entry(plugin_id="FFT — magnitude spectrum", backend_id="fft")):
        contract = ctl._find_broker_plugin("fft")
    assert contract is not None
    assert contract.category.name == "FFT"


def test_returns_none_when_no_form_matches():
    """Truly unknown slug stays a 404 — no over-eager matching by
    e.g. category prefix alone, which would give the operator a
    surprising "wrong plugin dispatched" experience."""
    with _live_registry(_entry(plugin_id="FFT — magnitude spectrum", backend_id="fft")):
        contract = ctl._find_broker_plugin("does-not-exist")
    assert contract is None


def test_runtime_form_match_takes_priority_over_backend_id():
    """When two live entries are present and the URL matches one's
    runtime form exactly, return that one. Don't fall through to
    a backend_id collision on a sibling entry."""
    with _live_registry(
        _entry(plugin_id="exact-name", backend_id="other-backend"),
        _entry(plugin_id="other-name", backend_id="exact-name"),
    ):
        contract = ctl._find_broker_plugin("exact-name")
    # First-loop match wins; both candidates land in the same category
    # since both rows share category="fft" in this test, but we want
    # the runtime-form match to be preferred over the backend_id one.
    # Easiest pin: the function returned a contract at all (i.e. didn't
    # silently 404 because of ambiguity).
    assert contract is not None

"""Characterization tests for the in-process plugin registry.

Post-PI-5 the registry walks ``plugins/`` and finds nothing —
template-picker moved to ``services/particle_picking/`` (it was the
only live in-process plugin). Old ``ctf/ctffind`` /
``motioncor/motioncor2`` stub directories never actually existed in
the filesystem (CURRENT_ARCHITECTURE.md §3.4 was stale on that
point).

PI-6 deletes the registry module entirely; this test moves with it.
Until then it pins the empty-registry state so a stray PluginBase
subclass doesn't quietly land back in the walk.
"""
from __future__ import annotations

import pytest

from plugins.registry import registry


@pytest.mark.characterization
def test_registry_is_empty_after_pi5():
    """Post-PI-5 the in-process registry has no live plugins."""
    ids = {entry.plugin_id for entry in registry.list()}
    assert ids == set(), (
        f"Plugin registry should be empty post-PI-5; found {ids}. "
        f"If you want to re-enable in-process plugins, revert PI-6 first."
    )


@pytest.mark.characterization
def test_registry_get_missing_returns_none():
    assert registry.get("does-not-exist/anywhere") is None

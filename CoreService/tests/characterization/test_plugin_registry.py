"""Characterization tests for the plugin registry.

Pins which plugins auto-register and key bits of their PluginInfo so that
accidental reshuffling of the `plugins/` folder or a breaking PluginInfo
schema change is caught in CI.
"""
from __future__ import annotations

import pytest

from plugins.registry import registry


EXPECTED_PLUGIN_IDS = {
    "ctf/ctffind",
    "motioncor/motioncor2",
    "pp/template-picker",
}


@pytest.mark.characterization
def test_registered_plugin_ids():
    """The exact set of plugin IDs the registry exposes today."""
    ids = {entry.plugin_id for entry in registry.list()}
    assert ids == EXPECTED_PLUGIN_IDS, (
        f"Plugin registry drift: got {ids}, expected {EXPECTED_PLUGIN_IDS}. "
        f"If a plugin was added or removed intentionally, update this test."
    )


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id,expected_category,expected_name", [
    ("ctf/ctffind", "ctf", "ctffind"),
    ("motioncor/motioncor2", "motioncor", "motioncor2"),
    ("pp/template-picker", "pp", "template-picker"),
])
def test_plugin_entry_category_and_name(plugin_id, expected_category, expected_name):
    entry = registry.get(plugin_id)
    assert entry is not None
    assert entry.category == expected_category
    assert entry.name == expected_name


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", sorted(EXPECTED_PLUGIN_IDS))
def test_plugin_info_contract(plugin_id):
    """PluginInfo must expose the fields downstream code relies on."""
    entry = registry.get(plugin_id)
    info = entry.instance.get_info()
    assert info.name == entry.name
    assert info.version is not None
    # schema_version is how the frontend decides whether to re-fetch the input
    # form — it must always be present, even if just "1".
    assert info.schema_version is not None


@pytest.mark.characterization
@pytest.mark.parametrize("plugin_id", sorted(EXPECTED_PLUGIN_IDS))
def test_plugin_schemas_are_pydantic_classes(plugin_id):
    """input_schema() and output_schema() return Pydantic models, not instances."""
    entry = registry.get(plugin_id)
    from pydantic import BaseModel
    assert issubclass(entry.instance.input_schema(), BaseModel)
    assert issubclass(entry.instance.output_schema(), BaseModel)


@pytest.mark.characterization
def test_registry_get_missing_returns_none():
    assert registry.get("does-not-exist/anywhere") is None

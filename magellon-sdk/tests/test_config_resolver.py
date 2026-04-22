"""Unit tests for :class:`magellon_sdk.config.PluginConfigResolver` (G.3).

Pins the precedence chain: overrides > env > yaml > defaults >
call-site default. Plus the typed accessors (get_bool/get_int/
get_float/get_str) and apply_overrides merge semantics.

Every test uses ``monkeypatch`` for env so runs don't pollute each
other. Env-prefix defaults to ``MAGELLON_`` so a test key ``foo``
reads ``MAGELLON_FOO``.
"""
from __future__ import annotations

import pytest

from magellon_sdk.config import PluginConfigResolver


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------

def test_default_wins_when_no_other_layer_has_the_key():
    r = PluginConfigResolver(defaults={"max_res": 4.5})
    assert r.get("max_res") == 4.5


def test_yaml_beats_default():
    r = PluginConfigResolver(
        defaults={"max_res": 4.5},
        yaml_values={"max_res": 5.0},
    )
    assert r.get("max_res") == 5.0


def test_env_beats_yaml(monkeypatch):
    """Deployment-level override (env) wins over baked YAML."""
    monkeypatch.setenv("MAGELLON_MAX_RES", "6.0")
    r = PluginConfigResolver(
        defaults={"max_res": 4.5},
        yaml_values={"max_res": 5.0},
    )
    # Env always returns string; caller uses get_float for typing.
    assert r.get("max_res") == "6.0"
    assert r.get_float("max_res") == 6.0


def test_override_beats_env(monkeypatch):
    """Runtime bus push is the highest-priority layer."""
    monkeypatch.setenv("MAGELLON_MAX_RES", "6.0")
    r = PluginConfigResolver(
        defaults={"max_res": 4.5},
        yaml_values={"max_res": 5.0},
    )
    r.apply_overrides({"max_res": 7.5})
    assert r.get("max_res") == 7.5


def test_call_site_default_used_only_when_no_layer_has_the_key():
    r = PluginConfigResolver()
    assert r.get("missing", "fallback") == "fallback"
    assert r.get("missing") is None


# ---------------------------------------------------------------------------
# apply_overrides merge semantics
# ---------------------------------------------------------------------------

def test_apply_overrides_is_merge_not_replace():
    """Later pushes add to the override set; unreferenced keys keep
    their prior value."""
    r = PluginConfigResolver()
    r.apply_overrides({"a": 1, "b": 2})
    r.apply_overrides({"b": 99})
    assert r.get("a") == 1
    assert r.get("b") == 99


def test_apply_overrides_empty_dict_is_noop():
    r = PluginConfigResolver(defaults={"a": 1})
    r.apply_overrides({})
    assert r.get("a") == 1


def test_clear_overrides_drops_all_runtime_values():
    r = PluginConfigResolver(yaml_values={"a": "yaml"})
    r.apply_overrides({"a": "runtime"})
    assert r.get("a") == "runtime"
    r.clear_overrides()
    assert r.get("a") == "yaml"


# ---------------------------------------------------------------------------
# Typed accessors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("True", True), ("yes", True), ("on", True),
    ("0", False), ("false", False), ("no", False), ("off", False), ("", False),
])
def test_get_bool_interprets_string_truthiness(raw, expected):
    r = PluginConfigResolver(yaml_values={"flag": raw})
    assert r.get_bool("flag") is expected


def test_get_bool_passes_through_real_booleans():
    r = PluginConfigResolver(yaml_values={"a": True, "b": False})
    assert r.get_bool("a") is True
    assert r.get_bool("b") is False


def test_get_bool_returns_default_when_key_missing():
    r = PluginConfigResolver()
    assert r.get_bool("missing") is False
    assert r.get_bool("missing", default=True) is True


def test_get_int_coerces_strings_and_logs_on_garbage():
    r = PluginConfigResolver(yaml_values={"n": "42", "bad": "not-an-int"})
    assert r.get_int("n") == 42
    # Garbage falls back to default rather than raising; a plugin's
    # hot loop shouldn't crash on a typo'd config value.
    assert r.get_int("bad", default=7) == 7


def test_get_float_coerces_strings():
    r = PluginConfigResolver(yaml_values={"n": "4.5"})
    assert r.get_float("n") == 4.5


def test_get_str_stringifies_non_strings():
    r = PluginConfigResolver(yaml_values={"n": 42})
    assert r.get_str("n") == "42"


# ---------------------------------------------------------------------------
# Env prefix
# ---------------------------------------------------------------------------

def test_custom_env_prefix(monkeypatch):
    """Plugins in a custom namespace can scope their env vars."""
    monkeypatch.setenv("CTF_MAX_RES", "6.0")
    monkeypatch.setenv("MAGELLON_MAX_RES", "99")  # should be ignored
    r = PluginConfigResolver(env_prefix="CTF_")
    assert r.get("max_res") == "6.0"


def test_env_key_is_uppercased_with_prefix(monkeypatch):
    """Dotted / underscored / mixed-case keys all uppercase cleanly."""
    monkeypatch.setenv("MAGELLON_FOO_BAR", "hit")
    r = PluginConfigResolver()
    assert r.get("foo_bar") == "hit"


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

def test_snapshot_reflects_all_layers_with_override_precedence(monkeypatch):
    monkeypatch.setenv("MAGELLON_A", "env-a")
    monkeypatch.setenv("MAGELLON_B", "env-b")
    r = PluginConfigResolver(
        defaults={"a": "default-a", "c": "default-c"},
        yaml_values={"b": "yaml-b", "c": "yaml-c"},
    )
    r.apply_overrides({"c": "override-c"})

    snap = r.snapshot()

    # a: default < env → env wins
    assert snap["a"] == "env-a"
    # b: yaml < env → env wins
    assert snap["b"] == "env-b"
    # c: default < yaml < no env < override → override wins
    assert snap["c"] == "override-c"

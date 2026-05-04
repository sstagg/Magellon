"""Tests for PluginPortAllocator (R2 #4, 2026-05-04)."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from services.plugin_installer.port_allocator import (
    PluginPortAllocator,
    PortRangeExhausted,
)


# ---------------------------------------------------------------------------
# Fakes — bypass the real port-bind probe
# ---------------------------------------------------------------------------


def _all_ports_free(monkeypatch):
    monkeypatch.setattr(
        "services.plugin_installer.port_allocator._is_port_free",
        lambda port: True,
    )


def _no_ports_free(monkeypatch):
    monkeypatch.setattr(
        "services.plugin_installer.port_allocator._is_port_free",
        lambda port: False,
    )


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


def test_allocate_returns_a_port_in_range(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    port = allocator.allocate("template-picker")
    assert 18000 <= port <= 18099


def test_allocate_is_idempotent(tmp_path, monkeypatch):
    """Re-installing the same plugin returns the same port. Pinned
    so the announce envelope's URL stays stable across re-installs."""
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    first = allocator.allocate("template-picker")
    second = allocator.allocate("template-picker")
    assert first == second


def test_allocate_two_plugins_get_different_ports(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    a = allocator.allocate("a")
    b = allocator.allocate("b")
    assert a != b


def test_allocate_persists_assignment_across_instances(tmp_path, monkeypatch):
    """A new allocator pointed at the same plugins_dir reads the
    persisted file. Survives CoreService restart."""
    _all_ports_free(monkeypatch)
    a1 = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    p1 = a1.allocate("x")

    a2 = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    p2 = a2.allocate("x")
    assert p1 == p2


def test_release_frees_port_for_reuse(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18001)
    p_a = allocator.allocate("a")
    p_b = allocator.allocate("b")
    # Both ports in range used; releasing 'a' frees its port for a
    # third plugin.
    allocator.release("a")
    p_c = allocator.allocate("c")
    assert p_c == p_a


def test_allocate_raises_when_range_exhausted(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18001)
    allocator.allocate("a")
    allocator.allocate("b")
    with pytest.raises(PortRangeExhausted, match="bump MAGELLON_PLUGIN_PORT_MAX"):
        allocator.allocate("c")


def test_allocate_raises_when_all_ports_taken_by_other_processes(tmp_path, monkeypatch):
    """Range is empty assignments-wise but every port is bound by
    something else on the host — surface as exhaustion, not a silent
    pick of a port that won't actually bind."""
    _no_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18002)
    with pytest.raises(PortRangeExhausted):
        allocator.allocate("a")


def test_get_returns_assigned_port_or_none(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path)
    assert allocator.get("never-installed") is None
    p = allocator.allocate("here")
    assert allocator.get("here") == p


# ---------------------------------------------------------------------------
# Persistence layout
# ---------------------------------------------------------------------------


def test_state_file_format_is_json_dict(tmp_path, monkeypatch):
    _all_ports_free(monkeypatch)
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    allocator.allocate("plugin-1")
    state = json.loads((tmp_path / ".port_assignments.json").read_text())
    assert isinstance(state, dict)
    assert "plugin-1" in state


def test_corrupted_state_file_doesnt_crash(tmp_path, monkeypatch):
    """Garbage in .port_assignments.json → log + start fresh, not raise."""
    _all_ports_free(monkeypatch)
    (tmp_path / ".port_assignments.json").write_text("not json {{{", encoding="utf-8")
    allocator = PluginPortAllocator(tmp_path, port_min=18000, port_max=18099)
    p = allocator.allocate("post-corruption")
    assert 18000 <= p <= 18099


# ---------------------------------------------------------------------------
# Env override
# ---------------------------------------------------------------------------


def test_env_overrides_port_range(tmp_path, monkeypatch):
    """Operator can repoint the range without redeploying via env vars."""
    _all_ports_free(monkeypatch)
    monkeypatch.setenv("MAGELLON_PLUGIN_PORT_MIN", "30000")
    monkeypatch.setenv("MAGELLON_PLUGIN_PORT_MAX", "30001")
    allocator = PluginPortAllocator(tmp_path)
    p = allocator.allocate("env-tester")
    assert 30000 <= p <= 30001

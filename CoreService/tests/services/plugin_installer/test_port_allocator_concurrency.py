"""Port-allocator probes for concurrency + cross-method collisions.

The allocator's contract: two plugins on the same host get different
ports, even when one is installed via uv and the other via docker
(sharing the same ``plugins_dir`` and therefore the same
``.port_assignments.json``). Symmetric release. Exhaustion is a hard
error, not a silent zero.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from services.plugin_installer.port_allocator import (
    PluginPortAllocator,
    PortRangeExhausted,
)


# ---------------------------------------------------------------------------
# Cross-method collisions
# ---------------------------------------------------------------------------


class TestCrossMethodSharing:
    """UvInstaller and DockerInstaller share the same plugins_dir in
    production — both install under ``<plugins_dir>/<plugin_id>/`` —
    so their PluginPortAllocator instances must coordinate via the
    same on-disk assignment file."""

    def test_two_allocators_same_dir_do_not_collide(self, tmp_path):
        # Narrow the range so a collision would be highly likely if
        # they weren't coordinating.
        a = PluginPortAllocator(tmp_path, port_min=19000, port_max=19010)
        b = PluginPortAllocator(tmp_path, port_min=19000, port_max=19010)

        port_a = a.allocate("plugin-a")
        port_b = b.allocate("plugin-b")
        assert port_a != port_b

    def test_uv_release_then_docker_realloc_can_reuse_port(self, tmp_path):
        """A plugin uninstalled via uv frees its port; a subsequent
        docker install of a different plugin can grab the freed slot."""
        a = PluginPortAllocator(tmp_path, port_min=19020, port_max=19021)
        port_a = a.allocate("plugin-a")
        a.release("plugin-a")

        b = PluginPortAllocator(tmp_path, port_min=19020, port_max=19021)
        port_b = b.allocate("plugin-b")
        # With only 2 ports and one freed, the second allocate must
        # land — either at the freed slot or the other.
        assert port_b is not None
        assert 19020 <= port_b <= 19021


# ---------------------------------------------------------------------------
# Concurrency under threads
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """The allocator uses a module-level lock around the disk
    read/write. Concurrent allocations should produce distinct ports."""

    def test_concurrent_allocations_yield_distinct_ports(self, tmp_path):
        alloc = PluginPortAllocator(tmp_path, port_min=19050, port_max=19099)

        results: list[int] = []
        results_lock = threading.Lock()

        def worker(idx: int) -> None:
            port = alloc.allocate(f"plugin-{idx}")
            with results_lock:
                results.append(port)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 20 allocations should be distinct.
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_same_plugin_id_is_idempotent(self, tmp_path):
        """If 10 threads simultaneously call ``allocate('foo')``,
        every caller should see the same port — not 10 different ones."""
        alloc = PluginPortAllocator(tmp_path, port_min=19120, port_max=19140)

        results: list[int] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(10)

        def worker() -> None:
            barrier.wait()  # release all at once
            port = alloc.allocate("same-plugin")
            with results_lock:
                results.append(port)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1, (
            f"idempotent allocate should return one port for ten concurrent "
            f"calls, got {set(results)}"
        )


# ---------------------------------------------------------------------------
# Exhaustion — hard error, no silent zero
# ---------------------------------------------------------------------------


class TestExhaustion:
    def test_exhausted_range_raises(self, tmp_path):
        alloc = PluginPortAllocator(tmp_path, port_min=19200, port_max=19201)
        alloc.allocate("a")
        alloc.allocate("b")
        with pytest.raises(PortRangeExhausted):
            alloc.allocate("c")

    def test_exhausted_error_message_is_actionable(self, tmp_path):
        alloc = PluginPortAllocator(tmp_path, port_min=19210, port_max=19210)
        alloc.allocate("a")
        with pytest.raises(PortRangeExhausted) as exc_info:
            alloc.allocate("b")
        msg = str(exc_info.value)
        # Operator should learn what to do next.
        assert "MAGELLON_PLUGIN_PORT_MAX" in msg or "uninstall" in msg

    def test_invalid_range_rejected_at_construction(self, tmp_path):
        with pytest.raises(ValueError):
            PluginPortAllocator(tmp_path, port_min=19500, port_max=19499)


# ---------------------------------------------------------------------------
# Persistence — survives reconstruction
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_allocations_survive_reconstruction(self, tmp_path):
        a = PluginPortAllocator(tmp_path, port_min=19300, port_max=19310)
        port = a.allocate("survive-me")
        # Drop the allocator (simulate process restart) and rebuild.
        b = PluginPortAllocator(tmp_path, port_min=19300, port_max=19310)
        again = b.allocate("survive-me")
        assert again == port

    def test_release_removes_from_disk(self, tmp_path):
        a = PluginPortAllocator(tmp_path, port_min=19320, port_max=19330)
        a.allocate("ephemeral")
        a.release("ephemeral")
        # ``get`` should return None now.
        b = PluginPortAllocator(tmp_path, port_min=19320, port_max=19330)
        assert b.get("ephemeral") is None

    def test_state_file_corruption_starts_fresh_no_crash(self, tmp_path):
        a = PluginPortAllocator(tmp_path, port_min=19340, port_max=19350)
        a.allocate("first")
        # Corrupt the JSON file.
        (tmp_path / ".port_assignments.json").write_text("{not json")
        # Reconstruction should not crash; should also not return the
        # previous allocation since the data is unreadable.
        b = PluginPortAllocator(tmp_path, port_min=19340, port_max=19350)
        # ``get`` reads-once and returns None on unreadable.
        assert b.get("first") is None
        # ``allocate`` should still produce a valid port.
        fresh = b.allocate("fresh")
        assert 19340 <= fresh <= 19350

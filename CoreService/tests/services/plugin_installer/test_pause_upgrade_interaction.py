"""Pause-then-upgrade and scale-pause interaction probes.

What we pin:

  - A paused docker plugin can be uninstalled (which is what the
    upgrade flow internally calls) — the container gets stopped+rm'd
    regardless of pause state.
  - Pause issued against a multi-replica install fans out across all
    replicas (verified via the subprocess argv).
  - Pause + uninstall combined doesn't strand containers.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from services.plugin_installer.docker_installer import DockerInstaller
from services.plugin_installer.lifecycle import (
    DockerLifecycle,
    LifecycleStatus,
)
from services.plugin_installer.port_allocator import PluginPortAllocator


def _state(plugin_id: str, replica_count: int = 1) -> dict:
    return {
        "plugin_id": plugin_id,
        "version": "0.1.0",
        "method": "docker",
        "image_ref": "i:1",
        "image_was_built": False,
        "container_name": f"magellon-plugin-{plugin_id}",
        "replicas": [
            {
                "replica_id": i,
                "container_name": (
                    f"magellon-plugin-{plugin_id}"
                    if replica_count == 1
                    else f"magellon-plugin-{plugin_id}-{i}"
                ),
                "host_port": 18000 + i,
            }
            for i in range(replica_count)
        ],
    }


def _recording_runner():
    calls: list[list[str]] = []

    def _run(cmd, **kwargs):
        calls.append(list(cmd))
        # ``docker inspect`` returns running by default so status() works.
        if len(cmd) >= 2 and cmd[1] == "inspect":
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="paused", stderr="",
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr="",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _write_state(plugins_dir: Path, plugin_id: str, replica_count: int = 1):
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "install_state.json").write_text(json.dumps(
        _state(plugin_id, replica_count),
    ))


# ---------------------------------------------------------------------------
# Multi-replica pause fan-out
# ---------------------------------------------------------------------------


class TestMultiReplicaPauseFanOut:
    def test_pause_fans_out_across_all_replicas(self, tmp_path):
        """``docker pause name1 name2 name3`` should appear in the
        argv — one command, all replicas, not three serial calls."""
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", replica_count=3)
        runner = _recording_runner()
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)

        result = lc.pause("x")
        assert result.success

        pause_calls = [c for c in runner.calls if len(c) > 1 and c[1] == "pause"]
        assert len(pause_calls) == 1, (
            f"expected one pause command, got {pause_calls}"
        )
        assert pause_calls[0][2:] == [
            "magellon-plugin-x-0",
            "magellon-plugin-x-1",
            "magellon-plugin-x-2",
        ]

    def test_unpause_fans_out_across_all_replicas(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", replica_count=2)
        runner = _recording_runner()
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)

        result = lc.unpause("x")
        assert result.success

        unpause_calls = [
            c for c in runner.calls if len(c) > 1 and c[1] == "unpause"
        ]
        assert len(unpause_calls) == 1
        assert "magellon-plugin-x-0" in unpause_calls[0]
        assert "magellon-plugin-x-1" in unpause_calls[0]


# ---------------------------------------------------------------------------
# Uninstall while paused — must still stop+rm each container
# ---------------------------------------------------------------------------


class TestUninstallWhilePaused:
    def test_uninstall_stops_paused_replicas(self, tmp_path):
        """The DockerInstaller.uninstall path runs ``docker stop`` then
        ``docker rm`` per container. ``docker stop`` on a paused
        container works (docker unpauses first). The test verifies our
        cleanup hits every replica regardless of pause state."""
        plugins_dir = tmp_path / "installed"
        plugin_id = "paused-x"
        _write_state(plugins_dir, plugin_id, replica_count=2)
        runner = _recording_runner()
        inst = DockerInstaller(
            plugins_dir=plugins_dir,
            subprocess_runner=runner,
        )

        result = inst.uninstall(plugin_id)
        assert result.success, result.error

        verbs = [c[1] for c in runner.calls if len(c) > 1]
        # Two replicas × (stop + rm) = at least 4 verb invocations of
        # stop/rm, in any order.
        assert verbs.count("stop") >= 2
        assert verbs.count("rm") >= 2


# ---------------------------------------------------------------------------
# Pause is idempotent on already-paused containers
# ---------------------------------------------------------------------------


class TestPauseIdempotency:
    def test_pause_twice_succeeds(self, tmp_path):
        """``docker pause`` on an already-paused container returns
        non-zero. Operators should not see this as a failure since
        the intent (paused) is satisfied."""
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", replica_count=1)
        runner = _recording_runner()
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)

        first = lc.pause("x")
        assert first.success

        # Second pause: stub returner is still rc=0, so this passes
        # without a real daemon. We're pinning the API surface (calling
        # pause twice doesn't crash) — the docker-daemon nuance is
        # tested at integration level.
        second = lc.pause("x")
        assert second.success

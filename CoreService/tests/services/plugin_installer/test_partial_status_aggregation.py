"""``DockerLifecycle.status`` aggregation across multi-replica installs.

The aggregator returns:
  - RUNNING when all replicas are running
  - STOPPED when all replicas are stopped
  - PAUSED when all replicas are paused
  - PARTIAL when there's more than one replica in mixed states
  - UNKNOWN when a single replica is in a transitional state

These rules matter because the React UI uses the aggregate to flag
degraded availability to operators — a wrong aggregate = a silently
broken replica.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

import pytest

from services.plugin_installer.lifecycle import (
    DockerLifecycle,
    LifecycleStatus,
)


def _state_for(replicas: Iterable[str]) -> dict:
    """Build an ``install_state.json`` dict with N replicas."""
    replica_list = [
        {
            "replica_id": i,
            "container_name": f"magellon-plugin-x-{i}",
            "host_port": 18000 + i,
        }
        for i in range(len(list(replicas)))
    ]
    return {
        "plugin_id": "x",
        "version": "0.1.0",
        "method": "docker",
        "image_ref": "i:1",
        "image_was_built": False,
        "container_name": replica_list[0]["container_name"] if replica_list else "",
        "replicas": replica_list,
    }


def _stub_inspector(states_by_container: dict[str, str]):
    """Return a subprocess runner that responds to ``docker inspect -f
    '{{.State.Status}}' <name>`` with the configured per-container state."""

    def _run(cmd, **kwargs):
        if len(cmd) >= 4 and cmd[1] == "inspect" and cmd[2] == "-f":
            container = cmd[4]
            state = states_by_container.get(container, "exited")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=state, stderr="",
            )
        # Anything else (start/stop/restart) — fall through to success.
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return _run


def _write_state(plugins_dir: Path, plugin_id: str, replicas_per_state: list[str]):
    """Set up ``install_state.json`` for a plugin with N replicas."""
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True)
    state = _state_for(replicas_per_state)
    (plugin_dir / "install_state.json").write_text(json.dumps(state))
    return state


# ---------------------------------------------------------------------------
# Aggregate states
# ---------------------------------------------------------------------------


class TestAggregateStates:
    def test_all_running_aggregates_to_running(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running"] * 3)
        runner = _stub_inspector({
            f"magellon-plugin-x-{i}": "running" for i in range(3)
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.RUNNING

    def test_all_paused_aggregates_to_paused(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["paused"] * 3)
        runner = _stub_inspector({
            f"magellon-plugin-x-{i}": "paused" for i in range(3)
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.PAUSED

    def test_all_exited_aggregates_to_stopped(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["exited"] * 3)
        runner = _stub_inspector({
            f"magellon-plugin-x-{i}": "exited" for i in range(3)
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.STOPPED

    def test_two_running_one_exited_yields_partial(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running", "running", "exited"])
        runner = _stub_inspector({
            "magellon-plugin-x-0": "running",
            "magellon-plugin-x-1": "running",
            "magellon-plugin-x-2": "exited",
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.PARTIAL

    def test_running_plus_paused_yields_partial(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running", "paused"])
        runner = _stub_inspector({
            "magellon-plugin-x-0": "running",
            "magellon-plugin-x-1": "paused",
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.PARTIAL


# ---------------------------------------------------------------------------
# Edge — single replica in transitional state
# ---------------------------------------------------------------------------


class TestSingleReplicaTransitional:
    def test_single_replica_restarting_yields_unknown_not_partial(self, tmp_path):
        """Per lifecycle.py:274 a single replica in a transitional state
        must aggregate to UNKNOWN (not PARTIAL, which implies multi-replica
        degradation)."""
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["restarting"])
        runner = _stub_inspector({"magellon-plugin-x-0": "restarting"})
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.UNKNOWN

    def test_two_replicas_one_transitional_yields_partial(self, tmp_path):
        """With > 1 replica, a transitional one is degradation worth
        flagging — PARTIAL is the right answer."""
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running", "restarting"])
        runner = _stub_inspector({
            "magellon-plugin-x-0": "running",
            "magellon-plugin-x-1": "restarting",
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        assert lc.status("x") == LifecycleStatus.PARTIAL


# ---------------------------------------------------------------------------
# Phantom container — state file mentions a container docker doesn't know
# ---------------------------------------------------------------------------


class TestPhantomContainer:
    def test_phantom_in_state_aggregates_partial(self, tmp_path):
        """install_state.json says 3 replicas, but docker only knows
        about 2 (the third was manually ``docker rm``'d). The phantom's
        inspect returns non-zero, mapped to UNKNOWN per replica.
        Aggregate must catch the drift — PARTIAL."""
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running"] * 3)

        def _run(cmd, **kwargs):
            # Only replicas 0 and 1 exist; 2 returns non-zero.
            if len(cmd) >= 4 and cmd[1] == "inspect":
                container = cmd[4]
                if container == "magellon-plugin-x-2":
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=1, stdout="", stderr="no such container",
                    )
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="running", stderr="",
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=_run)
        assert lc.status("x") == LifecycleStatus.PARTIAL


# ---------------------------------------------------------------------------
# status_per_replica completeness
# ---------------------------------------------------------------------------


class TestStatusPerReplica:
    def test_returns_one_entry_per_replica(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        _write_state(plugins_dir, "x", ["running", "paused", "exited"])
        runner = _stub_inspector({
            "magellon-plugin-x-0": "running",
            "magellon-plugin-x-1": "paused",
            "magellon-plugin-x-2": "exited",
        })
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=runner)
        entries = lc.status_per_replica("x")
        assert len(entries) == 3
        assert {e["container_name"] for e in entries} == {
            "magellon-plugin-x-0",
            "magellon-plugin-x-1",
            "magellon-plugin-x-2",
        }
        # Status values map to enum strings.
        status_by_name = {e["container_name"]: e["status"] for e in entries}
        assert status_by_name["magellon-plugin-x-0"] == "running"
        assert status_by_name["magellon-plugin-x-1"] == "paused"
        assert status_by_name["magellon-plugin-x-2"] == "stopped"

    def test_missing_install_state_yields_unknown(self, tmp_path):
        """No install_state.json (plugin never installed under docker)
        — aggregate is UNKNOWN, per-replica list is empty."""
        plugins_dir = tmp_path / "installed"
        plugins_dir.mkdir()
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=_stub_inspector({}))
        assert lc.status("missing") == LifecycleStatus.UNKNOWN
        assert lc.status_per_replica("missing") == []

"""Tests for the host predicate evaluator (P4).

Predicate evaluation is what decides whether an install method
applies to the host. A bug here means the wrong installer is picked
silently — exactly the kind of regression that wastes hours in
production.
"""
from __future__ import annotations

import sys

import pytest

from services.plugin_installer.predicates import (
    HostInfo,
    collect_required_binaries,
    evaluate_predicates,
)


# ---------------------------------------------------------------------------
# evaluate_predicates — happy-path matrix
# ---------------------------------------------------------------------------

def test_empty_predicates_pass():
    """No requirements = trivially supported on every host."""
    assert evaluate_predicates([], HostInfo()) == []


def test_docker_daemon_predicate_match():
    host = HostInfo(docker_daemon=True)
    assert evaluate_predicates([{"docker_daemon": True}], host) == []


def test_docker_daemon_predicate_mismatch():
    """No daemon → docker install methods rejected. The error
    message must say what was wanted vs got so operators don't
    have to reverse-engineer the predicate."""
    host = HostInfo(docker_daemon=False)
    failed = evaluate_predicates([{"docker_daemon": True}], host)
    assert len(failed) == 1
    assert "want True" in failed[0]
    assert "got False" in failed[0]


def test_binary_predicate_match():
    host = HostInfo(binaries_on_path=["ctffind4", "MotionCor2"])
    assert evaluate_predicates([{"binary": "ctffind4"}], host) == []


def test_binary_predicate_mismatch():
    host = HostInfo(binaries_on_path=["MotionCor2"])
    failed = evaluate_predicates([{"binary": "ctffind4"}], host)
    assert len(failed) == 1
    assert "ctffind4" in failed[0]
    assert "PATH" in failed[0]


def test_python_predicate_match():
    """Plugin's manifest says ``python: ">=3.11"`` and host runs
    3.12 → pass."""
    host = HostInfo(python_version="3.12.3")
    assert evaluate_predicates([{"python": ">=3.11"}], host) == []


def test_python_predicate_mismatch():
    host = HostInfo(python_version="3.10.5")
    failed = evaluate_predicates([{"python": ">=3.11"}], host)
    assert len(failed) == 1
    assert "3.10" in failed[0]


def test_python_predicate_invalid_value():
    host = HostInfo(python_version="3.12.3")
    # A non-string value (operator typo'd a list) must fail closed,
    # not crash.
    failed = evaluate_predicates([{"python": ["3.11", "3.12"]}], host)
    assert len(failed) == 1
    assert "SemVer range string" in failed[0]


def test_gpu_count_min_predicate_match():
    host = HostInfo(gpu_count=4)
    assert evaluate_predicates([{"gpu_count_min": 1}], host) == []
    assert evaluate_predicates([{"gpu_count_min": 4}], host) == []


def test_gpu_count_min_predicate_mismatch():
    host = HostInfo(gpu_count=0)
    failed = evaluate_predicates([{"gpu_count_min": 1}], host)
    assert "want ≥1" in failed[0]


def test_os_predicate_match():
    host = HostInfo(os="linux")
    assert evaluate_predicates([{"os": "linux"}], host) == []


def test_os_predicate_mismatch():
    host = HostInfo(os="windows")
    failed = evaluate_predicates([{"os": "linux"}], host)
    assert "linux" in failed[0] and "windows" in failed[0]


def test_arch_predicate_match():
    host = HostInfo(arch="x86_64")
    assert evaluate_predicates([{"arch": "x86_64"}], host) == []


# ---------------------------------------------------------------------------
# Composite + edge cases
# ---------------------------------------------------------------------------

def test_multiple_predicates_all_must_pass():
    """Several predicates in one install entry — every one must
    pass for the method to apply (AND semantics, not OR)."""
    host = HostInfo(docker_daemon=True, binaries_on_path=["ctffind4"])
    predicates = [{"docker_daemon": True}, {"binary": "ctffind4"}]
    assert evaluate_predicates(predicates, host) == []


def test_multiple_predicates_partial_failure_lists_only_failures():
    host = HostInfo(docker_daemon=True, binaries_on_path=[])  # no ctffind4
    predicates = [{"docker_daemon": True}, {"binary": "ctffind4"}]
    failed = evaluate_predicates(predicates, host)
    assert len(failed) == 1
    assert "ctffind4" in failed[0]


def test_unknown_predicate_fails_closed():
    """An unknown predicate key must NOT silently pass — operators
    typo'ing a predicate name should see the install refused, not
    accidentally let it through."""
    host = HostInfo()
    failed = evaluate_predicates([{"unicorn": True}], host)
    assert len(failed) == 1
    assert "unknown predicate" in failed[0]
    assert "unicorn" in failed[0]


def test_malformed_predicate_fails():
    """Predicates are single-key dicts. A list, a multi-key dict,
    or a bare string must fail visibly."""
    host = HostInfo()
    failed = evaluate_predicates([
        {"docker_daemon": True, "binary": "x"},  # multi-key
    ], host)
    assert len(failed) == 1
    assert "malformed" in failed[0]


# ---------------------------------------------------------------------------
# collect_required_binaries
# ---------------------------------------------------------------------------

def test_collect_required_binaries_finds_each_unique_name():
    """The manager passes this list to detect_host_info so we only
    probe what's actually needed (enumerating PATH is slow + pointless)."""
    install_predicates = [
        [{"docker_daemon": True}],
        [{"python": ">=3.11"}, {"binary": "ctffind4"}],
        [{"binary": "MotionCor2"}, {"binary": "ctffind4"}],
    ]
    binaries = collect_required_binaries(install_predicates)
    assert binaries == ["MotionCor2", "ctffind4"]


def test_collect_required_binaries_ignores_non_binary_predicates():
    install_predicates = [
        [{"docker_daemon": True}, {"gpu_count_min": 2}, {"os": "linux"}],
    ]
    assert collect_required_binaries(install_predicates) == []

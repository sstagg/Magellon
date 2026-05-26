"""Tests for the install pipeline factory wiring.

Pins the plugins_install_dir resolution order: env override beats
configured setting beats hard-coded default. The setting in
``configs/app_settings_*.yaml`` is the production path; the env
override exists for ad-hoc operational tweaks.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from services.plugin_installer.factory import (
    _build_runtime_config,
    _default_plugins_dir,
    _liveness_health_check,
    reset_factory,
)


def test_env_override_wins_over_settings(monkeypatch):
    """``MAGELLON_PLUGINS_INSTALL_DIR`` is the operational override —
    it must beat the YAML so an operator can repoint the install dir
    without redeploying."""
    monkeypatch.setenv("MAGELLON_PLUGINS_INSTALL_DIR", "/tmp/from-env")
    fake_settings = SimpleNamespace(
        directory_settings=SimpleNamespace(PLUGINS_DIR="/should-not-win"),
    )
    with mock.patch("config.app_settings", fake_settings):
        assert _default_plugins_dir() == Path("/tmp/from-env")


def test_configured_setting_wins_when_env_missing(monkeypatch):
    """When no env override, the YAML-configured setting wins over
    the hard-coded default. Verifies the new fluent-config wiring."""
    monkeypatch.delenv("MAGELLON_PLUGINS_INSTALL_DIR", raising=False)
    fake_settings = SimpleNamespace(
        directory_settings=SimpleNamespace(PLUGINS_DIR="/configured/path"),
    )
    with mock.patch("config.app_settings", fake_settings):
        assert _default_plugins_dir() == Path("/configured/path")


def test_falls_back_to_hardcoded_default_when_neither(monkeypatch):
    monkeypatch.delenv("MAGELLON_PLUGINS_INSTALL_DIR", raising=False)
    fake_settings = SimpleNamespace(
        directory_settings=SimpleNamespace(PLUGINS_DIR=None),
    )
    with mock.patch("config.app_settings", fake_settings):
        assert _default_plugins_dir() == Path("/var/magellon/plugins/installed")


def test_settings_relative_path_resolves_under_gpfs():
    """End-to-end: a relative PLUGINS_DIR in YAML becomes an absolute
    path under MAGELLON_GPFS_PATH after the DirectorySettings validator
    runs. Verifies the validator was extended to cover PLUGINS_DIR."""
    from models.pydantic_models_settings import DirectorySettings

    settings = DirectorySettings(
        MAGELLON_GPFS_PATH="/gpfs",
        PLUGINS_DIR="plugins",
    )
    assert settings.PLUGINS_DIR == "/gpfs/plugins"


def test_settings_absolute_path_passes_through():
    """An absolute PLUGINS_DIR in YAML must NOT be re-rooted under
    gpfs — operators may legitimately want a non-gpfs location for the
    install dir (e.g. a faster local disk for venv builds)."""
    from models.pydantic_models_settings import DirectorySettings

    settings = DirectorySettings(
        MAGELLON_GPFS_PATH="/gpfs",
        PLUGINS_DIR="/opt/magellon/plugins",
    )
    assert settings.PLUGINS_DIR == "/opt/magellon/plugins"


def test_runtime_config_uses_gpfs_path_not_home(monkeypatch):
    """Installed plugins must receive the GPFS data-plane root, not the
    CoreService home subdirectory inside GPFS."""
    monkeypatch.delenv("MAGELLON_GPFS_PATH", raising=False)
    fake_settings = SimpleNamespace(
        rabbitmq_settings=SimpleNamespace(
            USER_NAME="rabbit",
            PASSWORD="secret",
            HOST_NAME="rmq",
            PORT=5672,
            VIRTUAL_HOST="/",
        ),
        directory_settings=SimpleNamespace(
            MAGELLON_GPFS_PATH="C:/magellon/gpfs",
            MAGELLON_HOME_DIR="C:/magellon/gpfs/home",
        ),
    )
    with mock.patch("config.app_settings", fake_settings):
        runtime = _build_runtime_config()

    assert runtime.gpfs_root == "C:/magellon/gpfs"


# ---------------------------------------------------------------------------
# _liveness_health_check matching
# ---------------------------------------------------------------------------


def _entry(*, plugin_id="x", category="x", backend_id=None):
    """Build a stub PluginLivenessEntry-shaped object — health check
    only reads three fields so a SimpleNamespace is enough."""
    return SimpleNamespace(plugin_id=plugin_id, category=category, backend_id=backend_id)


def test_health_check_matches_by_plugin_id():
    """The trivial case — entry.plugin_id == requested plugin_id."""
    registry = SimpleNamespace(list_live=lambda: [_entry(plugin_id="fft", category="fft")])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        assert _liveness_health_check("fft", 0.5) is True


def test_health_check_matches_by_category():
    """Pre-PI: single-backend categories (CTF, MotionCor, FFT) match
    via category == plugin_id since their PluginInfo.name doesn't
    line up with the manifest archive_id."""
    registry = SimpleNamespace(list_live=lambda: [
        _entry(plugin_id="fft/fft", category="fft", backend_id=None),
    ])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        assert _liveness_health_check("fft", 0.5) is True


def test_health_check_matches_by_backend_id():
    """Multi-backend categories (particle_picking with template-picker /
    topaz / boxnet siblings) — category alone is ambiguous; match
    against the announce envelope's backend_id so each sibling's
    install handshake completes on its own row."""
    registry = SimpleNamespace(list_live=lambda: [
        _entry(
            plugin_id="particle_picking/Template Picker",
            category="particle_picking",
            backend_id="template-picker",
        ),
    ])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        assert _liveness_health_check("template-picker", 0.5) is True


def test_health_check_matches_by_normalized_substring():
    """Topaz announces two separate (category, name) pairs from a single
    manifest — topaz_particle_picking + micrograph_denoising. The
    announce envelope doesn't always carry backend_id back, so the
    matcher needs a last-resort: plugin_id appears as a normalized
    substring of entry.plugin_id."""
    registry = SimpleNamespace(list_live=lambda: [
        _entry(
            plugin_id="topazparticlepicking/Topaz Particle Picking",
            category="topazparticlepicking",
            backend_id=None,
        ),
    ])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        assert _liveness_health_check("topaz", 0.5) is True


def test_health_check_substring_match_requires_min_length():
    """Don't fuzzy-match plugin_ids shorter than 4 chars — too many
    false positives (e.g. ``fft`` would match any 'soft', 'shift', etc.)."""
    registry = SimpleNamespace(list_live=lambda: [
        _entry(plugin_id="something/Soft Plugin", category="other", backend_id=None),
    ])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        # "ft" (2 chars) would substring-match "Soft" but the gate blocks
        # — and there's no other field to match on either.
        assert _liveness_health_check("ft", 0.05) is False


def test_health_check_times_out_when_nothing_announces():
    """No matching announce → return False once deadline passes."""
    registry = SimpleNamespace(list_live=lambda: [])
    with mock.patch("magellon_sdk.bus.services.liveness_registry.get_registry",
                    return_value=registry):
        assert _liveness_health_check("ghost", 0.05) is False

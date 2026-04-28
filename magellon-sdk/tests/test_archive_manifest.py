"""Tests for ``magellon_sdk.archive.manifest`` v1.

Pin the manifest contract:

  - v1 fields round-trip through YAML
  - Backward-compat aliases for the old ``schema_version: int`` and
    ``sdk_compat: str`` field names (existing CoreService callers
    in plugins/controller.py and core/plugin_catalog.py rely on these)
  - Backward-compat synthesis of a single-entry ``install:`` list
    from a legacy ``image: {ref: ...}`` field
  - Validation rejections for the things the install controller
    would reject anyway (bad slug, non-v7 UUID, empty install,
    unknown method, missing method-specific fields)
  - sdk_compat / schema_version property aliases on the model
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import yaml

from magellon_sdk.archive.manifest import (
    HealthCheckSpec,
    InstallSpec,
    PluginArchiveManifest,
    ResourceHints,
    SchemaVersionError,
    SdkCompatError,
    UISpec,
    check_sdk_compat,
    dump_manifest_yaml,
    load_manifest_yaml,
    uuid7,
)


# ---------------------------------------------------------------------------
# UUID v7 helpers
# ---------------------------------------------------------------------------

def test_uuid7_returns_a_v7_uuid():
    """The pack CLI relies on this for archive_id auto-generation —
    a regression that quietly returned v4 would let archives ship
    with non-time-sortable ids, breaking the hub's natural ordering."""
    u = uuid7()
    assert u.version == 7


def test_uuid7_is_time_sortable():
    """Two UUIDs minted seconds apart must compare in time order
    when treated as ints. That's the whole point of v7 — the hub
    indexes archives by archive_id and expects newest first to be
    the largest int."""
    import time as _time
    a = uuid7()
    _time.sleep(0.005)  # 5ms — well above v7's ms timestamp resolution
    b = uuid7()
    assert int(b) > int(a)


# ---------------------------------------------------------------------------
# Minimal valid v1 manifest
# ---------------------------------------------------------------------------

def _minimal_v1_manifest() -> dict:
    return {
        "manifest_version": "1",
        "plugin_id": "ctffind4",
        "archive_id": str(uuid7()),
        "name": "CTFfind v4",
        "version": "1.0.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "ctf",
        "install": [
            {
                "method": "docker",
                "image": "ghcr.io/magellon/ctffind4:1.0.0",
                "requires": [{"docker_daemon": True}],
            },
        ],
    }


def test_minimal_v1_manifest_validates():
    m = PluginArchiveManifest.model_validate(_minimal_v1_manifest())
    assert m.plugin_id == "ctffind4"
    assert m.requires_sdk == ">=2.0,<3.0"
    assert m.install[0].method == "docker"
    assert m.install[0].image == "ghcr.io/magellon/ctffind4:1.0.0"


def test_yaml_round_trip():
    """The pack CLI writes manifest.yaml; the install controller
    reads it back. The round-trip must preserve every field."""
    original = PluginArchiveManifest.model_validate(_minimal_v1_manifest())
    text = dump_manifest_yaml(original)
    reloaded = load_manifest_yaml(text)

    assert reloaded.plugin_id == original.plugin_id
    assert reloaded.archive_id == original.archive_id
    assert reloaded.requires_sdk == original.requires_sdk
    assert reloaded.install[0].method == "docker"


# ---------------------------------------------------------------------------
# Backward-compat: old field names accepted on input
# ---------------------------------------------------------------------------

def test_accepts_legacy_schema_version_int():
    """v0 archives wrote ``schema_version: 1`` (integer). Loading
    them must still work — production has v0 archives in flight."""
    data = _minimal_v1_manifest()
    del data["manifest_version"]
    data["schema_version"] = 1

    m = PluginArchiveManifest.model_validate(data)
    assert m.manifest_version == "1"
    assert m.schema_version == 1  # legacy property still works


def test_accepts_legacy_sdk_compat_field_name():
    """``sdk_compat`` was the v0 name; renamed to ``requires_sdk`` in
    v1. Existing plugin-catalog callers reference ``manifest.sdk_compat``
    so the property alias must continue to resolve."""
    data = _minimal_v1_manifest()
    del data["requires_sdk"]
    data["sdk_compat"] = ">=1.0,<2.0"

    m = PluginArchiveManifest.model_validate(data)
    assert m.requires_sdk == ">=1.0,<2.0"
    assert m.sdk_compat == ">=1.0,<2.0"  # legacy property still works


def test_accepts_legacy_image_field_synthesizes_install_list():
    """v0 archives had a single ``image: {ref: ...}`` instead of an
    ordered ``install:`` list. The model_validator synthesizes a
    single-entry docker install so old archives still load."""
    data = {
        "manifest_version": "1",
        "plugin_id": "old-plugin",
        "archive_id": str(uuid7()),
        "name": "Old Plugin",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "image": {"ref": "ghcr.io/old/plugin:0.1.0"},
        # No 'install:' field — must be synthesized.
    }
    m = PluginArchiveManifest.model_validate(data)
    assert len(m.install) == 1
    assert m.install[0].method == "docker"
    assert m.install[0].image == "ghcr.io/old/plugin:0.1.0"


def test_install_takes_precedence_over_legacy_image():
    """If both ``install:`` AND ``image:`` are present (mid-migration
    plugin), trust the new ``install:`` field — that's where the
    plugin author put their current intent."""
    data = _minimal_v1_manifest()
    data["image"] = {"ref": "ghcr.io/should-be-ignored:0.0.0"}

    m = PluginArchiveManifest.model_validate(data)
    assert m.install[0].image == "ghcr.io/magellon/ctffind4:1.0.0"


# ---------------------------------------------------------------------------
# Validation rejections
# ---------------------------------------------------------------------------

def test_rejects_bad_plugin_id_with_uppercase():
    data = _minimal_v1_manifest()
    data["plugin_id"] = "CTFfind4"
    with pytest.raises(ValueError, match="lowercase"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_bad_plugin_id_with_spaces():
    data = _minimal_v1_manifest()
    data["plugin_id"] = "ctffind 4"
    with pytest.raises(ValueError, match="lowercase"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_uppercase_category():
    data = _minimal_v1_manifest()
    data["category"] = "CTF"
    with pytest.raises(ValueError, match="lowercase"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_unknown_manifest_version():
    """A future-versioned archive arriving at an old SDK must fail
    fast with a clear error, not silently load with garbage defaults.

    Pydantic v2 wraps custom ValueError subclasses (SchemaVersionError)
    in ValidationError; the surface message is what matters for
    plugin authors debugging a refused archive."""
    data = _minimal_v1_manifest()
    data["manifest_version"] = "99"
    with pytest.raises(ValueError, match="not supported"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_non_uuid_v7_archive_id():
    """Hand-written UUID v4 in archive_id is the most likely
    mistake — operators copy a UUID from elsewhere. The validator
    catches it so the hub doesn't end up with un-sortable archives."""
    from uuid import uuid4
    data = _minimal_v1_manifest()
    data["archive_id"] = str(uuid4())  # v4, not v7
    with pytest.raises(ValueError, match="UUID v7"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_empty_install_list():
    """An archive with no install method is unusable — the install
    controller would have nothing to dispatch to. Fail at parse time."""
    data = _minimal_v1_manifest()
    data["install"] = []
    with pytest.raises(ValueError, match="install"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_unknown_install_method():
    data = _minimal_v1_manifest()
    data["install"] = [{"method": "snake-oil"}]
    with pytest.raises(ValueError, match="unknown install method"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_docker_install_without_image_or_dockerfile():
    """A docker install entry must say what to run."""
    data = _minimal_v1_manifest()
    data["install"] = [{"method": "docker"}]
    with pytest.raises(ValueError, match="image.*dockerfile"):
        PluginArchiveManifest.model_validate(data)


def test_rejects_uv_install_without_pyproject():
    data = _minimal_v1_manifest()
    data["install"] = [{"method": "uv"}]
    with pytest.raises(ValueError, match="pyproject"):
        PluginArchiveManifest.model_validate(data)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_archive_id_auto_generated_if_missing():
    """The pack CLI passes ``archive_id`` explicitly. A hand-written
    manifest passed through the model gets one auto-generated so
    plugin authors don't have to know how to make a UUID v7."""
    data = _minimal_v1_manifest()
    del data["archive_id"]
    m = PluginArchiveManifest.model_validate(data)
    assert m.archive_id.version == 7


def test_default_requires_includes_broker_and_gpfs():
    """Most plugins need both. The default reflects the common case
    so authors don't have to remember to write it."""
    data = _minimal_v1_manifest()
    m = PluginArchiveManifest.model_validate(data)
    assert "broker" in m.requires
    assert "gpfs" in m.requires


def test_default_health_check():
    """30s timeout matches the heartbeat default (15s × 2)."""
    data = _minimal_v1_manifest()
    m = PluginArchiveManifest.model_validate(data)
    assert m.health_check.timeout_seconds == 30
    assert m.health_check.expected_announce is True


def test_default_ui_is_none():
    """v1 reserves ui: but doesn't load custom React components.
    Default null means 'use the existing schema-driven form'."""
    data = _minimal_v1_manifest()
    m = PluginArchiveManifest.model_validate(data)
    assert m.ui is None


def test_default_resources_zero_gpu():
    """Most plugins are CPU-only. Defaulting gpu_count to 0 means
    a plugin author has to opt INTO requiring a GPU host — failing
    safely on CPU-only deployments."""
    data = _minimal_v1_manifest()
    m = PluginArchiveManifest.model_validate(data)
    assert m.resources.gpu_count == 0


# ---------------------------------------------------------------------------
# check_sdk_compat (kept from v0 — legacy callers depend on it)
# ---------------------------------------------------------------------------

def test_check_sdk_compat_passes_in_range():
    check_sdk_compat(">=2.0,<3.0", "2.1.0")


def test_check_sdk_compat_raises_below_minimum():
    with pytest.raises(SdkCompatError, match="< required"):
        check_sdk_compat(">=2.0,<3.0", "1.9.0")


def test_check_sdk_compat_raises_above_maximum():
    with pytest.raises(SdkCompatError, match="not < allowed"):
        check_sdk_compat(">=2.0,<3.0", "3.0.0")


def test_check_sdk_compat_unparseable():
    """Empty or junk input must fail — silently passing on a typo
    would mask compatibility breaks."""
    with pytest.raises(SdkCompatError, match="unparseable"):
        check_sdk_compat("garbage", "2.0.0")

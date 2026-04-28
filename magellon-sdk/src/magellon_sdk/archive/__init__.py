"""Plugin archive format — `.mpn` archives, v1.

A `.mpn` (Magellon Plugin) is a zip containing a ``manifest.yaml`` at
its root plus the plugin's source / Dockerfile / schemas / docs.
CoreService's install controller reads the manifest, picks an install
method, and brings the plugin live.

See ``Documentation/PLUGIN_ARCHIVE_FORMAT.md`` for the full spec.

Backward-compat note: pre-v1 archives used ``.magplugin`` extension
and ``plugin.yaml`` filename. The pack CLI writes the new canonical
names but the loader accepts either; existing CoreService callers
(``plugins/controller.py``, ``core/plugin_catalog.py``) keep working
unchanged.
"""
from __future__ import annotations

from magellon_sdk.archive.manifest import (
    CURRENT_SCHEMA_VERSION,
    HealthCheckSpec,
    InstallSpec,
    PluginArchiveManifest,
    ResourceHints,
    SchemaVersionError,
    SdkCompatError,
    SUPPORTED_MANIFEST_VERSIONS,
    UISpec,
    check_sdk_compat,
    dump_manifest_yaml,
    load_manifest_bytes,
    load_manifest_yaml,
    uuid7,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "HealthCheckSpec",
    "InstallSpec",
    "PluginArchiveManifest",
    "ResourceHints",
    "SchemaVersionError",
    "SdkCompatError",
    "SUPPORTED_MANIFEST_VERSIONS",
    "UISpec",
    "check_sdk_compat",
    "dump_manifest_yaml",
    "load_manifest_bytes",
    "load_manifest_yaml",
    "uuid7",
]

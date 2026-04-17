"""Plugin archive format (H3a).

A ``.magplugin`` archive is a zip containing a ``plugin.yaml`` manifest
plus an optional ``README.md``. CoreService's ``POST /plugins/install/archive``
endpoint accepts such archives, parses the manifest, and spawns a
container using the metadata.

Scope notes:

- The archive currently only describes **where to pull the image from**
  (``image.ref``) plus install defaults. It does NOT carry the image
  payload, source, or Dockerfile — those arrive in H2.b / H3 follow-ups
  when build-from-source is implemented. For now the operator (or a
  future central registry) is responsible for publishing the referenced
  image to a registry CoreService can pull from.

- The schema is versioned independently from ``magellon-sdk`` via
  ``schema_version: int``. Bump on breaking shape changes. Within a
  major SDK version we promise schema_version 1 readers keep working.

- SDK compatibility is declared in the manifest via ``sdk_compat``
  (a PEP 440 / SemVer-style version specifier). CoreService refuses to
  install an archive whose SDK pin excludes this deployment's SDK —
  fail-fast is safer than silent data-shape drift at runtime.
"""
from __future__ import annotations

from magellon_sdk.archive.manifest import (
    ArchiveImage,
    ArchiveInstallDefaults,
    ArchiveVolumeSpec,
    PluginArchiveManifest,
    SchemaVersionError,
    SdkCompatError,
    check_sdk_compat,
    load_manifest_bytes,
    load_manifest_yaml,
)

__all__ = [
    "ArchiveImage",
    "ArchiveInstallDefaults",
    "ArchiveVolumeSpec",
    "PluginArchiveManifest",
    "SchemaVersionError",
    "SdkCompatError",
    "check_sdk_compat",
    "load_manifest_bytes",
    "load_manifest_yaml",
]

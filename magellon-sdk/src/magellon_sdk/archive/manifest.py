"""Plugin archive manifest (``plugin.yaml``).

See :mod:`magellon_sdk.archive` package docstring for the overall
archive shape and scoping decisions.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


# Current archive-manifest schema version. Bump on breaking shape
# changes. Readers must validate schema_version <= their max supported
# version before parsing fields.
CURRENT_SCHEMA_VERSION = 1


class SchemaVersionError(ValueError):
    """Raised when a manifest's schema_version is newer than we understand."""


class SdkCompatError(ValueError):
    """Raised when a manifest's sdk_compat pin excludes the running SDK."""


class ArchiveVolumeSpec(BaseModel):
    """Default volume mount declared by the archive author.

    CoreService merges these with any request-time overrides at install
    time. Hosts typically localize ``host`` to their own filesystem
    before installing.
    """

    host: str
    container: str
    read_only: bool = False


class ArchiveInstallDefaults(BaseModel):
    """Install-time defaults. Everything here is overridable at
    ``POST /plugins/install/archive`` time — the archive is a
    suggestion, not a hard constraint."""

    env: Dict[str, str] = Field(default_factory=dict)
    volumes: List[ArchiveVolumeSpec] = Field(default_factory=list)
    network: Optional[str] = None


class ArchiveImage(BaseModel):
    """Where CoreService pulls the plugin's image from.

    H3a only supports ref-based images. Build-from-source is a
    follow-up (would add ``source: path/in/archive`` + ``dockerfile``
    fields).
    """

    ref: str = Field(..., description="Docker image reference, e.g. ghcr.io/org/plugin:v1")


class PluginArchiveManifest(BaseModel):
    """Top-level manifest shape.

    Field validators enforce conservative invariants so the review
    workflow (H3b) can reject obviously-broken archives before a human
    looks at them.
    """

    schema_version: int = Field(
        CURRENT_SCHEMA_VERSION,
        description="Archive-manifest schema version. Bump on breaking shape change.",
    )
    plugin_id: str = Field(
        ...,
        description="Stable id used on the bus; matches PluginInfo.name. "
        "Lowercase letters / digits / '.' / '-' / '_' only.",
    )
    name: str = Field(..., description="Human display name.")
    version: str = Field(..., description="Plugin version (SemVer recommended).")
    category: str = Field(
        ...,
        description="Magellon category, lowercase (fft / ctf / motioncor / pp / ...).",
    )
    sdk_compat: str = Field(
        ...,
        description="SDK version specifier the plugin was built for. "
        "Accepts PEP 440 / SemVer-style specifiers like '>=1.0,<2.0'.",
    )
    image: ArchiveImage
    install_defaults: ArchiveInstallDefaults = Field(
        default_factory=ArchiveInstallDefaults
    )
    description: str = ""
    developer: str = ""
    license: str = ""

    @field_validator("plugin_id")
    @classmethod
    def _plugin_id_slug(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9._-]+", v):
            raise ValueError(
                "plugin_id must be lowercase letters/digits/dot/dash/underscore "
                "(no spaces, no slashes, no uppercase). Slugify your display name."
            )
        return v

    @field_validator("category")
    @classmethod
    def _category_lower(cls, v: str) -> str:
        if v != v.lower():
            raise ValueError("category must be lowercase (e.g. 'fft', not 'FFT')")
        return v

    @field_validator("schema_version")
    @classmethod
    def _known_schema(cls, v: int) -> int:
        if v < 1 or v > CURRENT_SCHEMA_VERSION:
            raise SchemaVersionError(
                f"unknown schema_version {v} — this SDK understands "
                f"1..{CURRENT_SCHEMA_VERSION}"
            )
        return v


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_manifest_yaml(text: str) -> PluginArchiveManifest:
    """Parse a YAML manifest string."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("plugin.yaml must be a YAML mapping at the top level")
    return PluginArchiveManifest.model_validate(data)


def load_manifest_bytes(data: bytes) -> PluginArchiveManifest:
    """Parse a raw ``plugin.yaml`` byte blob (as extracted from the zip)."""
    return load_manifest_yaml(data.decode("utf-8"))


# ---------------------------------------------------------------------------
# SDK compat check
# ---------------------------------------------------------------------------

_SPEC_CLAUSE = re.compile(r"(>=|<=|>|<|==|!=)\s*([0-9.]+)")


def _parse_version(v: str) -> tuple:
    """Parse "1", "1.2", "1.2.3" into a left-padded (major, minor, patch)
    tuple. Two-part versions are common in pin clauses (``>=1.0,<2.0``);
    requiring full SemVer triples just to compare them is fussy."""
    parts = v.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError(f"cannot parse version {v!r}")
    nums = [int(p) for p in parts]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def check_sdk_compat(sdk_compat: str, running_version: str) -> None:
    """Raise :class:`SdkCompatError` if ``running_version`` doesn't
    satisfy ``sdk_compat``.

    Implements a minimal subset of PEP 440 that covers the common
    plugin-author case: comma-separated clauses, each with one of
    ``>=`` ``<=`` ``>`` ``<`` ``==`` ``!=``. No wildcards, no pre-
    releases. Over-engineering a full resolver is a waste when the
    archive ecosystem is this narrow; widen later if plugin authors
    legitimately need caret/tilde.
    """
    clauses = _SPEC_CLAUSE.findall(sdk_compat)
    if not clauses:
        raise SdkCompatError(f"unparseable sdk_compat {sdk_compat!r}")
    running = _parse_version(running_version)
    for op, v in clauses:
        required = _parse_version(v)
        if op == ">=" and running < required:
            raise SdkCompatError(f"SDK {running_version} < required {v}")
        elif op == ">" and running <= required:
            raise SdkCompatError(f"SDK {running_version} not > required {v}")
        elif op == "<=" and running > required:
            raise SdkCompatError(f"SDK {running_version} > allowed ≤ {v}")
        elif op == "<" and running >= required:
            raise SdkCompatError(f"SDK {running_version} not < allowed {v}")
        elif op == "==" and running != required:
            raise SdkCompatError(f"SDK {running_version} != required {v}")
        elif op == "!=" and running == required:
            raise SdkCompatError(f"SDK {running_version} excluded by != {v}")


__all__ = [
    "ArchiveImage",
    "ArchiveInstallDefaults",
    "ArchiveVolumeSpec",
    "CURRENT_SCHEMA_VERSION",
    "PluginArchiveManifest",
    "SchemaVersionError",
    "SdkCompatError",
    "check_sdk_compat",
    "load_manifest_bytes",
    "load_manifest_yaml",
]

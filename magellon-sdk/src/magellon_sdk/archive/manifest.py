"""Plugin archive manifest (``manifest.yaml``) — v1.

This is the **archive** manifest — the file at the root of a ``.mpn``
plugin archive that describes who the plugin is, how to install it,
and what it needs from the deployment. Distinct from
:class:`magellon_sdk.models.manifest.PluginManifest`, which is the
**runtime** manifest a plugin's ``manifest()`` method returns; the
two are independent shapes with different lifecycles.

See ``Documentation/PLUGIN_ARCHIVE_FORMAT.md`` for the full spec.
The Pydantic model below is the source of truth; the doc and the
model must agree, with the model winning ties.

Backward compatibility
======================

Pre-v1 manifests used ``schema_version: int`` and ``sdk_compat: str``.
v1 renames these to ``manifest_version: str`` and ``requires_sdk:
str`` but accepts the old names on input via Pydantic aliases. The
``sdk_compat`` and ``schema_version`` attribute getters still resolve
so the existing CoreService callers (``plugins/controller.py``,
``core/plugin_catalog.py``) keep working without edits.

Pre-v1 also had a single ``image: {ref: ...}`` field. v1 replaces it
with the ordered ``install: [...]`` list. A model validator
synthesizes a single-entry install list when only the legacy
``image:`` is provided, so old manifests still load.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import yaml
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Compatibility constants
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 1
"""Legacy alias for backward compat — controller.py imports this."""

SUPPORTED_MANIFEST_VERSIONS: tuple[str, ...] = ("1",)
"""Whatever string values ``manifest_version:`` may take. Bump when
adding a new format major; keep the old strings here so we can read
old archives until explicit drop."""


class SchemaVersionError(ValueError):
    """Raised when a manifest's manifest_version isn't one we understand."""


class SdkCompatError(ValueError):
    """Raised when a manifest's requires_sdk pin excludes the running SDK."""


# ---------------------------------------------------------------------------
# UUID v7 — generation + validation
# ---------------------------------------------------------------------------

def uuid7() -> UUID:
    """Generate a UUID v7 (time-ordered) per RFC 9562.

    Python's stdlib doesn't ship UUID v7 generation until 3.13; we
    implement it here so the pack CLI doesn't need a third-party
    dependency. Layout:

      bits  0-47: unix timestamp in milliseconds
      bits 48-51: version field (= 7)
      bits 52-63: rand_a (12 random bits)
      bits 64-65: variant field (= 0b10)
      bits 66-127: rand_b (62 random bits)

    Time-sortable so the hub can list "newest first" without a
    separate index column.
    """
    ts_ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    val = (
        (ts_ms & 0xFFFFFFFFFFFF) << 80
        | 0x7 << 76
        | rand_a << 64
        | 0x2 << 62
        | rand_b
    )
    return UUID(int=val)


def _is_uuid_v7(u: UUID) -> bool:
    return u.version == 7


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ResourceHints(BaseModel):
    """Hints the install controller uses to pick a host."""

    model_config = ConfigDict(extra="ignore")

    cpu_cores: Optional[int] = None
    memory_mb: Optional[int] = None
    gpu_count: int = 0
    gpu_memory_mb: Optional[int] = None
    typical_duration_seconds: Optional[int] = None


class HealthCheckSpec(BaseModel):
    """How the install controller verifies the plugin came up."""

    model_config = ConfigDict(extra="ignore")

    timeout_seconds: int = 30
    """How long the controller waits for the plugin's first announce
    before declaring the install failed. Increase for plugins that
    take a long time to initialize (e.g. preloading a CUDA model)."""

    expected_announce: bool = True
    """The plugin is expected to announce on the discovery exchange.
    A False value here is reserved for plugins that don't run as a
    bus consumer (none today)."""


class UISpec(BaseModel):
    """v1 only allows a docs link. Custom React component injection
    is reserved for v2 (post-trust-tier hub)."""

    model_config = ConfigDict(extra="ignore")

    docs_url: Optional[str] = None


class InstallSpec(BaseModel):
    """One viable install path. Each archive can declare several;
    the install controller picks the first whose ``requires:``
    predicates the host satisfies."""

    model_config = ConfigDict(extra="forbid")

    method: str
    """``docker``, ``uv``, or ``subprocess`` (subprocess reserved
    for v2)."""

    # Docker-specific fields
    image: Optional[str] = None
    """Pre-built image reference, e.g. ``ghcr.io/.../ctffind4:1.2.3``."""

    dockerfile: Optional[str] = None
    """Relative path to Dockerfile inside the archive. If both
    ``image:`` and ``dockerfile:`` are set, the controller prefers
    ``image:`` (faster install — no build step)."""

    build_context: Optional[str] = "."
    """Build context relative to the archive root. Only consulted
    when ``dockerfile:`` is used."""

    # uv-specific fields
    pyproject: Optional[str] = None
    """Relative path to pyproject.toml (or requirements.txt) for uv
    install."""

    requires: List[Dict[str, Any]] = Field(default_factory=list)
    """Predicates the host must satisfy for this install method to
    apply. Each item is a single-key dict like ``{"docker_daemon": true}``,
    ``{"binary": "ctffind4"}``, ``{"python": ">=3.11"}``,
    ``{"gpu_count_min": 1}``, ``{"os": "linux"}``. The install
    controller evaluates these in order; first install entry whose
    predicates all pass wins."""

    @field_validator("method")
    @classmethod
    def _known_method(cls, v: str) -> str:
        if v not in {"docker", "uv", "subprocess"}:
            raise ValueError(
                f"unknown install method {v!r}; expected docker, uv, or subprocess"
            )
        return v

    @model_validator(mode="after")
    def _check_method_fields(self) -> "InstallSpec":
        if self.method == "docker":
            if not self.image and not self.dockerfile:
                raise ValueError(
                    "docker install method requires either 'image' or 'dockerfile'"
                )
        elif self.method == "uv":
            if not self.pyproject:
                raise ValueError("uv install method requires 'pyproject'")
        return self


# ---------------------------------------------------------------------------
# Top-level manifest
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[a-z0-9._-]+")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PluginArchiveManifest(BaseModel):
    """The manifest at the root of every ``.mpn`` archive.

    Every field validator either rejects something the install
    controller would reject anyway (so plugin authors fail fast) or
    normalizes input (lowercasing category, parsing UUIDs).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # -- format version (accepts old `schema_version: int` too) ---------
    manifest_version: str = Field(
        default="1",
        validation_alias=AliasChoices("manifest_version", "schema_version"),
        description="Archive manifest format version. v0 archives sent integer "
        "schema_version=1; v1 archives send string manifest_version='1'.",
    )

    # -- identity -------------------------------------------------------
    plugin_id: str = Field(
        ...,
        description="Slug used in subjects, provenance, logs, UI labels. "
        "Stable across versions. Lowercase letters/digits/'.'/'-'/'_'.",
    )
    archive_id: UUID = Field(
        default_factory=uuid7,
        description="UUID v7 — machine identity for THIS build. Time-sortable. "
        "New per build; pack CLI generates one if missing.",
    )

    # -- versioning -----------------------------------------------------
    name: str = Field(..., description="Human display name.")
    version: str = Field(..., description="Plugin version (SemVer recommended).")
    requires_sdk: str = Field(
        ...,
        validation_alias=AliasChoices("requires_sdk", "sdk_compat"),
        description="Compatible SDK version range, e.g. '>=2.0,<3.0'. "
        "Install controller refuses on mismatch.",
    )

    # -- authorship -----------------------------------------------------
    author: str = Field(default="", description="Plugin author / contact.")
    copyright: str = ""
    description: str = ""
    homepage: Optional[str] = None
    license: str = Field(default="", description="SPDX identifier (e.g. MIT, BSD-3-Clause).")

    # -- timestamps -----------------------------------------------------
    created: datetime = Field(default_factory=_now_utc)
    updated: datetime = Field(default_factory=_now_utc)

    # -- classification -------------------------------------------------
    category: str = Field(
        ...,
        description="Lowercase TaskCategory name (fft, ctf, motioncor, pp, ...).",
    )
    backend_id: Optional[str] = Field(
        default=None,
        description="Substitutable identity within category (Track C). "
        "Two plugins with the same backend_id collide loudly in the "
        "liveness registry.",
    )

    # -- deployment requirements ----------------------------------------
    requires: List[str] = Field(
        default_factory=lambda: ["broker", "gpfs"],
        description="What the plugin needs from the deployment. The install "
        "controller refuses if any required surface is unavailable. "
        "Common values: 'broker', 'gpfs', 'db'.",
    )

    # -- resource hints --------------------------------------------------
    resources: ResourceHints = Field(default_factory=ResourceHints)

    # -- schemas (relative paths inside the archive) --------------------
    input_schema: str = "schemas/input.json"
    output_schema: str = "schemas/output.json"

    # -- install methods (ordered preference) ---------------------------
    install: List[InstallSpec] = Field(
        default_factory=list,
        description="Ordered list — first install method whose 'requires:' "
        "predicates the host satisfies wins.",
    )

    # -- health check ---------------------------------------------------
    health_check: HealthCheckSpec = Field(default_factory=HealthCheckSpec)

    # -- UI integration -------------------------------------------------
    ui: Optional[UISpec] = None

    # -- file integrity (filled in by `plugin pack`) --------------------
    checksum_algorithm: str = "sha256"
    file_checksums: Dict[str, str] = Field(default_factory=dict)

    # -- discovery / search ---------------------------------------------
    tags: List[str] = Field(default_factory=list)
    replaces: List[str] = Field(
        default_factory=list,
        description="plugin_ids this archive supersedes (rare; for forks).",
    )
    deprecates: List[str] = Field(default_factory=list)

    # -- legacy v0 fields kept for input compat -------------------------
    # When set on input WITHOUT an 'install:' list, a model_validator
    # synthesizes a single-entry install list from them.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("manifest_version", mode="before")
    @classmethod
    def _normalize_manifest_version(cls, v: Any) -> str:
        """Accept old integer schema_version=1 by stringifying."""
        if isinstance(v, int):
            return str(v)
        return v

    @field_validator("manifest_version")
    @classmethod
    def _supported_version(cls, v: str) -> str:
        if v not in SUPPORTED_MANIFEST_VERSIONS:
            raise SchemaVersionError(
                f"manifest_version {v!r} not supported by this SDK; "
                f"known: {list(SUPPORTED_MANIFEST_VERSIONS)}"
            )
        return v

    @field_validator("plugin_id")
    @classmethod
    def _plugin_id_slug(cls, v: str) -> str:
        if not _SLUG_RE.fullmatch(v):
            raise ValueError(
                "plugin_id must be lowercase letters/digits/dot/dash/underscore "
                "(no spaces, no slashes, no uppercase)."
            )
        return v

    @field_validator("archive_id")
    @classmethod
    def _archive_id_is_v7(cls, v: UUID) -> UUID:
        if not _is_uuid_v7(v):
            raise ValueError(
                f"archive_id must be a UUID v7 (got version={v.version}); "
                f"the pack CLI generates one — don't hand-write."
            )
        return v

    @field_validator("category")
    @classmethod
    def _category_lower(cls, v: str) -> str:
        if v != v.lower():
            raise ValueError("category must be lowercase (e.g. 'fft', not 'FFT')")
        return v

    @model_validator(mode="before")
    @classmethod
    def _legacy_image_to_install(cls, data: Any) -> Any:
        """Accept v0's ``image: {ref: ...}`` shape when ``install:`` is
        empty/missing. Synthesizes a single-entry docker install."""
        if not isinstance(data, dict):
            return data
        legacy_image = data.get("image")
        if data.get("install"):
            return data  # v1 already; ignore any stray ``image:``
        if isinstance(legacy_image, dict) and legacy_image.get("ref"):
            data = dict(data)
            data["install"] = [
                {
                    "method": "docker",
                    "image": legacy_image["ref"],
                    "requires": [{"docker_daemon": True}],
                }
            ]
            data.pop("image", None)
        return data

    @model_validator(mode="after")
    def _install_non_empty(self) -> "PluginArchiveManifest":
        if not self.install:
            raise ValueError(
                "install: must list at least one install method "
                "(docker / uv / subprocess)"
            )
        return self

    # ------------------------------------------------------------------
    # Backward-compat property aliases
    # ------------------------------------------------------------------

    @property
    def sdk_compat(self) -> str:
        """Deprecated alias for ``requires_sdk``. Kept for the existing
        controller.py and plugin_catalog.py callers."""
        return self.requires_sdk

    @property
    def schema_version(self) -> int:
        """Deprecated alias for ``int(manifest_version)``."""
        return int(self.manifest_version)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_manifest_yaml(text: str) -> PluginArchiveManifest:
    """Parse a YAML manifest string."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must be a YAML mapping at the top level")
    return PluginArchiveManifest.model_validate(data)


def load_manifest_bytes(data: bytes) -> PluginArchiveManifest:
    """Parse raw ``manifest.yaml`` bytes (e.g., extracted from a zip)."""
    return load_manifest_yaml(data.decode("utf-8"))


def dump_manifest_yaml(manifest: PluginArchiveManifest) -> str:
    """Serialize a manifest back to YAML — used by the pack CLI to
    write the final manifest into the archive after stamping
    ``archive_id``, ``updated``, and ``file_checksums``."""
    payload = manifest.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False)


# ---------------------------------------------------------------------------
# SDK compat check
# ---------------------------------------------------------------------------

_SPEC_CLAUSE = re.compile(r"(>=|<=|>|<|==|!=)\s*([0-9.]+)")


def _parse_version(v: str) -> tuple[int, int, int]:
    """Parse "1", "1.2", "1.2.3" into a (major, minor, patch) tuple,
    left-padded with zeros."""
    parts = v.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError(f"cannot parse version {v!r}")
    nums = [int(p) for p in parts]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])  # type: ignore[return-value]


def check_sdk_compat(requires_sdk: str, running_version: str) -> None:
    """Raise :class:`SdkCompatError` if ``running_version`` doesn't
    satisfy ``requires_sdk``.

    Minimal subset of PEP 440: comma-separated clauses each with one
    of ``>=`` ``<=`` ``>`` ``<`` ``==`` ``!=``. No wildcards / no
    pre-releases. Widen later if plugin authors need caret/tilde.
    """
    clauses = _SPEC_CLAUSE.findall(requires_sdk)
    if not clauses:
        raise SdkCompatError(f"unparseable requires_sdk {requires_sdk!r}")
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

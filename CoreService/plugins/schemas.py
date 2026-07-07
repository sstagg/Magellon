"""Request/response models for the plugins HTTP surface.

Pure Pydantic shapes — no registry, bus, or Docker access. Split out
of controller.py so the wire contract is readable in one place and the
route/service modules can share it without import cycles.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    Transport,
)


class PluginSummary(BaseModel):
    """Discovery payload — identity + the capability fields a UI / manager
    needs to decide *whether* and *how* to call this plugin.

    The full manifest is also fetchable at /plugins/{id}/manifest, but
    embedding the small high-signal subset here means the discovery
    endpoint is enough to render a plugin picker / health dashboard
    without N round-trips."""
    plugin_id: str
    category: str
    name: str
    version: str
    schema_version: str
    description: str
    developer: str
    # Capability subset surfaced into discovery — full manifest at /manifest
    capabilities: list[Capability] = Field(default_factory=list)
    supported_transports: list[Transport] = Field(default_factory=list)
    default_transport: Transport = Transport.RMQ
    isolation: IsolationLevel = IsolationLevel.CONTAINER
    # PI-6 retired the CoreService in-process registry. Every entry on
    # this surface is an external broker plugin announced via liveness.
    kind: Literal["broker"] = "broker"
    # Operator state (H1). ``enabled`` defaults True until an operator
    # toggles it. ``is_default_for_category`` is derived from the
    # per-category default-impl selection — the UI uses it to render
    # a "Default" badge and to decide which impl a category-scoped
    # dispatch would pick today.
    enabled: bool = True
    is_default_for_category: bool = False
    # Plugin-declared task queue (SDK 1.1+ Announce.task_queue). ``None``
    # for pre-1.1 plugins; the dispatcher falls back to the legacy
    # category-scoped route in that case.
    task_queue: Optional[str] = None


class JobSubmitRequest(BaseModel):
    """Submit one job for a plugin. ``input`` shape is validated by the plugin."""
    input: Dict[str, Any]
    name: Optional[str] = None
    image_id: Optional[str] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None
    """Pin dispatch to a specific backend within the plugin's category.
    When set and no live broker backend matches, the controller returns
    503 instead of round-robining."""
    parent_run_id: Optional[uuid.UUID] = None
    """Optional PipelineRun rollup the new job belongs to (Phase 8 /
    2026-05-04 reviewer-flagged Medium #6). Pre-Phase-8 callers leave
    None → job lands as a standalone run; UI rollup view shows it
    alone. Pipeline orchestrators set this so children link back to
    the parent rollup via ImageJob.parent_run_id."""


class BatchSubmitRequest(BaseModel):
    """Fan out the same plugin over many inputs (one job per input)."""
    inputs: List[Dict[str, Any]] = Field(..., min_length=1)
    name: Optional[str] = None
    image_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None
    parent_run_id: Optional[uuid.UUID] = None


# ---------------------------------------------------------------------------
# Capabilities — one consolidated catalog (X.1)
# ---------------------------------------------------------------------------
#
# UI and dispatcher both need the same picture: which categories exist,
# which backends serve each, which is default. Today this is split across
# GET /plugins/, GET /plugins/categories/defaults, and GET
# /plugins/{id}/manifest — three reads + a join in JS. /capabilities
# returns one snapshot.

class _BackendSummary(BaseModel):
    """One backend serving a category. Folds plugin + manifest + state."""

    backend_id: str
    plugin_id: str
    """``<category>/<short>`` form to match the rest of the discovery API."""
    name: str
    version: str
    schema_version: str
    description: str = ""
    developer: str = ""
    capabilities: list[Capability] = Field(default_factory=list)
    isolation: IsolationLevel = IsolationLevel.CONTAINER
    default_transport: Transport = Transport.RMQ
    live_replicas: int
    enabled: bool
    is_default_for_category: bool
    task_queue: Optional[str] = None


class _CategoryCapabilities(BaseModel):
    code: int
    name: str
    description: str
    default_backend: Optional[str] = None
    backends: list[_BackendSummary] = []
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    subject_kind: str = "image"
    """PE1-A: surfaced from CategoryContract.subject_kind so the
    catalog UI and workflow composer can answer "what subject does
    this category operate on?" without parsing the input schema."""
    produces_subject_kind: Optional[str] = None
    """PE1-A: from CategoryContract.produces_subject_kind. ``None``
    means the output subject is the same as the input — only
    transforming categories (PARTICLE_EXTRACTION) populate it."""
    input_subjects: Dict[str, str] = {}
    """PE1-B (2026-05-11): surfaced from CategoryContract.input_subjects.
    Maps input field name → subject-kind tag. The catalog's
    "what consumes ParticleStack?" filter reads this; the dispatcher
    uses the same map to validate UUID-typed inputs."""
    output_subjects: Dict[str, str] = {}
    """PE1-B: from CategoryContract.output_subjects. Maps output
    field name → subject-kind tag. The catalog's "which output is
    the produced-artifact OID?" answer reads this — distinguishes
    a scalar summary from the artifact reference."""
    examples: list[Dict[str, Any]] = []
    """Gradio-style pre-filled examples from CategoryContract.examples.
    Each entry is ``{name, description, values}`` — the React test
    panel lets operators pick one to populate the form in a single
    click. Empty list for categories that haven't authored examples
    yet."""


class _CapabilitiesResponse(BaseModel):
    sdk_version: str
    categories: list[_CategoryCapabilities] = []


class _SetDefaultRequest(BaseModel):
    plugin_id: str


class _InstallVolume(BaseModel):
    host_path: str
    container_path: str
    read_only: bool = False


class _InstallPluginRequest(BaseModel):
    """Everything docker run needs. Everything config-ish the plugin
    itself reads from its own settings YAML — not our problem here."""
    image_ref: str = Field(..., description="Docker image ref, e.g. ghcr.io/org/plugin:v1")
    env: Dict[str, str] = Field(default_factory=dict)
    volumes: List[_InstallVolume] = Field(default_factory=list)
    network: Optional[str] = Field(
        default=None,
        description="Docker network name. Use the network RMQ is on "
                    "(e.g. 'magellon_default' under docker-compose) so "
                    "the plugin can resolve rabbitmq by hostname.",
    )


class _CatalogInstallResponse(BaseModel):
    """POST /catalog/{catalog_id}/install response shape."""
    install: Dict[str, Any]
    catalog_id: str

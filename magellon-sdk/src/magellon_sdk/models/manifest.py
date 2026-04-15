"""Plugin manifest — the capability-aware extension of :class:`PluginInfo`.

A manifest tells the host (CoreService's plugin manager) three things:

1. *What the plugin is* — identity + version (carried via :class:`PluginInfo`).
2. *What it needs to run* — resource hints that decide where it can live
   (a CPU-only FFT can run in-process; an 8k×8k×75-frame MotionCor cannot).
3. *How it can be reached* — which transports it accepts so the manager
   can switch HTTP↔RMQ↔in-process per environment without code changes.

The manifest is derived from the plugin code (developer-authored) but
serializes cleanly to JSON for remote plugins to publish over their HTTP
``/plugins/<id>/manifest`` endpoint or register with Consul. That makes
in-house and containerized plugins describable in the *same* language —
the manager doesn't care which side of a network boundary the plugin
lives on.

Design notes
------------
- Capabilities are flags, not a tree. A plugin is GPU-required *and*
  memory-heavy; encoding that as a single enum hides the truth.
- :class:`Transport` lists what the plugin *supports*. The manager picks
  one based on per-environment config + availability. A plugin that
  declares ``IN_PROCESS`` does so as a hint — the host still has the
  final say (e.g. a sandboxed deployment may forbid in-process plugins).
- :class:`IsolationLevel` is the minimum the plugin requires. A plugin
  may declare ``CONTAINER`` to mean "do not import me into the host
  process under any circumstance" (MotionCor's case).
- ``replaces`` and ``deprecates`` make plugin upgrades a manifest
  concern, not an out-of-band coordination problem.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from magellon_sdk.models.plugin import PluginInfo


class Capability(str, Enum):
    """Behavioral / resource flags advertised by the plugin.

    Add new flags conservatively — every flag is a thing the manager
    must know how to interpret. Prefer composing existing flags over
    inventing finer-grained ones.
    """

    GPU_REQUIRED = "gpu_required"          # cannot run without a CUDA device
    GPU_OPTIONAL = "gpu_optional"          # uses GPU when present, falls back to CPU
    CPU_INTENSIVE = "cpu_intensive"        # multi-second per item, schedule with care
    MEMORY_INTENSIVE = "memory_intensive"  # >2 GB resident; do not run in-process
    LONG_RUNNING = "long_running"          # >60s per item; HTTP transport unwise
    IDEMPOTENT = "idempotent"              # safe to retry; manager may auto-retry
    PROGRESS_REPORTING = "progress_reporting"
    CANCELLABLE = "cancellable"            # honors JobCancelledError checkpoint


class Transport(str, Enum):
    """How the host can dispatch a job to this plugin.

    A plugin lists every transport its runtime supports. The host's
    config picks one per environment.
    """

    IN_PROCESS = "in_process"  # call PluginBase.run() in the host's thread pool
    HTTP = "http"              # POST to /plugins/<id>/jobs[/batch] on a sidecar
    RMQ = "rmq"                # enqueue TaskDto on the plugin's RMQ work queue
    NATS = "nats"              # publish task envelope to JetStream subject


class IsolationLevel(str, Enum):
    """Minimum isolation the plugin requires.

    Ordered from least to most isolation. The host will pick a
    deployment shape at or above this level. A plugin that requires
    ``CONTAINER`` must never be loaded in-process even if the host
    happens to have its dependencies installed.
    """

    IN_PROCESS = "in_process"  # OK to run in the host process
    PROCESS = "process"        # separate OS process (subprocess), same host
    CONTAINER = "container"    # separate container (Docker/Kubernetes pod)
    REMOTE = "remote"          # different host entirely (e.g. dedicated GPU node)


class ResourceHints(BaseModel):
    """Best-effort resource estimates per *one job invocation*.

    These are advisory — the manager uses them for scheduling decisions
    (don't pack 4 MotionCor jobs onto one GPU box, don't run a memory-
    heavy plugin in-process), not for hard quota enforcement.
    """

    memory_mb: Optional[int] = Field(
        default=None,
        description="Peak resident memory expected per job, in MB",
    )
    gpu_count: int = Field(
        default=0,
        ge=0,
        description="Number of GPUs required per job (0 = CPU-only)",
    )
    gpu_memory_mb: Optional[int] = Field(
        default=None,
        description="Per-GPU memory required, in MB",
    )
    cpu_cores: Optional[int] = Field(
        default=None,
        description="Suggested CPU cores per job",
    )
    typical_duration_seconds: Optional[float] = Field(
        default=None,
        description="P50 wall-clock for one job — informs transport choice "
                    "(<5s ⇒ HTTP fine, >60s ⇒ prefer RMQ)",
    )


class PluginManifest(BaseModel):
    """The full capability-aware description of a plugin.

    Built by :meth:`PluginBase.manifest` from the plugin's :class:`PluginInfo`,
    declared :class:`Capability` set, supported :class:`Transport` list,
    minimum :class:`IsolationLevel`, and :class:`ResourceHints`.

    Round-trips through JSON so a remote plugin can publish its manifest
    to the host (HTTP GET / Consul KV / NATS request) and the host can
    consume it with the exact same model.
    """

    info: PluginInfo
    capabilities: List[Capability] = Field(default_factory=list)
    supported_transports: List[Transport] = Field(
        default_factory=lambda: [Transport.IN_PROCESS],
        description="Transports the plugin's runtime accepts. The host "
                    "config decides which one to actually use.",
    )
    default_transport: Transport = Field(
        default=Transport.IN_PROCESS,
        description="Transport the plugin author considers optimal "
                    "(may be overridden by host config).",
    )
    isolation: IsolationLevel = Field(
        default=IsolationLevel.IN_PROCESS,
        description="Minimum isolation level required. A plugin marked "
                    "CONTAINER will never be loaded in-process by the host.",
    )
    resources: ResourceHints = Field(default_factory=ResourceHints)
    replaces: List[str] = Field(
        default_factory=list,
        description="Plugin ids this plugin can substitute for (same "
                    "input/output schema). Lets the manager swap "
                    "implementations without caller changes.",
    )
    deprecates: List[str] = Field(
        default_factory=list,
        description="Older versions / ids that this one obsoletes; the "
                    "manager should prefer this manifest over them.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form labels for filtering (e.g. 'imaging', 'beta')",
    )

    def has_capability(self, cap: Capability) -> bool:
        return cap in self.capabilities

    def supports(self, transport: Transport) -> bool:
        return transport in self.supported_transports

    def can_run_in_process(self) -> bool:
        """True iff the plugin's isolation requirement *allows* in-process
        execution. The host still has to *want* in-process and the
        plugin has to *support* the IN_PROCESS transport."""
        return self.isolation == IsolationLevel.IN_PROCESS


__all__ = [
    "Capability",
    "IsolationLevel",
    "PluginManifest",
    "ResourceHints",
    "Transport",
]

"""Base class for all Magellon processing plugins.

Every plugin backend (template picker, CTF, MotionCor, etc.) subclasses
``PluginBase`` and implements the abstract methods. The host
(controller / job manager / worker) interacts with plugins exclusively
through this interface.

This module is part of the stable SDK surface — changes here are
breaking changes for every plugin and require a major-version bump.

Lifecycle
---------
                  ┌─────────────────────────────────────────────┐
                  │        check_requirements()                 │
                  │               │                             │
    DISCOVERED ──►│  INSTALLED ──►│  configure() ──► CONFIGURED │
                  │               │                     │       │
                  │               │              setup()│       │
                  │               │                     ▼       │
                  │               │                   READY     │
                  │               │                  ┌──┴──┐    │
                  │               │       pre_execute│     │    │
                  │               │           execute│     │    │
                  │               │      post_execute│     │    │
                  │               │                  ▼     │    │
                  │               │      COMPLETED/ERROR   │    │
                  │               │          │   retry─────┘    │
                  │               │          │                  │
                  │               │     teardown()              │
                  │               │          │                  │
                  │               │       DISABLED / FAILED     │
                  └─────────────────────────────────────────────┘

Usage:

    plugin = MyPlugin()
    reqs = plugin.check_requirements()      # verify env
    plugin.configure(settings)              # apply config
    plugin.setup()                          # one-time init
    output = plugin.run(validated_input)    # pre + execute + post
    plugin.teardown()                       # cleanup
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel

from magellon_sdk.models import (
    PluginInfo,
    PluginStatus,
    RecuirementResultEnum,
    RequirementResult,
    TaskCategory,
)
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    PluginManifest,
    ResourceHints,
    Transport,
)
from magellon_sdk.progress import NullReporter, ProgressReporter

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class PluginBase(ABC, Generic[InputT, OutputT]):
    """Strict contract that every Magellon plugin must implement.

    Type parameters
    ---------------
    InputT : BaseModel subclass — validated input for execute()
    OutputT : BaseModel subclass — validated output from execute()
    """

    task_category: ClassVar[TaskCategory]

    def __init__(self) -> None:
        self._status: PluginStatus = PluginStatus.DISCOVERED
        self._config: Dict[str, Any] = {}

    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Return plugin identity and version metadata."""
        ...

    @classmethod
    @abstractmethod
    def input_schema(cls) -> Type[InputT]:
        """Return the Pydantic model class used to validate input."""
        ...

    @classmethod
    @abstractmethod
    def output_schema(cls) -> Type[OutputT]:
        """Return the Pydantic model class used to validate output."""
        ...

    def check_requirements(self) -> List[RequirementResult]:
        """Verify that runtime dependencies are available.

        Override to check for libraries, GPU drivers, external binaries, etc.
        Default implementation succeeds unconditionally.
        """
        self._status = PluginStatus.INSTALLED
        return [
            RequirementResult(
                result=RecuirementResultEnum.SUCCESS,
                message="No special requirements",
            )
        ]

    def configure(self, settings: Dict[str, Any] | None = None) -> None:
        """Apply external configuration before first use."""
        if settings:
            self._config.update(settings)
        self._status = PluginStatus.CONFIGURED

    def setup(self) -> None:
        """One-time initialisation after configure()."""
        self._status = PluginStatus.READY

    def teardown(self) -> None:
        """Release resources acquired in setup()."""
        self._status = PluginStatus.DISABLED

    def pre_execute(self, input_data: InputT) -> InputT:
        """Hook called before execute(). Return the (possibly modified) input."""
        return input_data

    @abstractmethod
    def execute(
        self,
        input_data: InputT,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> OutputT:
        """Core processing — the only method every plugin must implement.

        ``reporter`` is always supplied by the host; plugins may call
        ``reporter.report(percent, message)`` at stage boundaries to stream
        progress. A :class:`NullReporter` is passed when no job context
        exists, so plugins can ignore the parameter safely.
        """
        ...

    def post_execute(self, input_data: InputT, output_data: OutputT) -> OutputT:
        """Hook called after execute(). Return the (possibly modified) output."""
        return output_data

    def run(
        self,
        raw_input: Dict[str, Any] | InputT,
        *,
        reporter: Optional[ProgressReporter] = None,
    ) -> OutputT:
        """Validated execution pipeline: validate → pre → execute → post → validate.

        This is the method the host calls. It enforces the Pydantic
        contracts on both sides and manages status transitions.
        """
        effective_reporter: ProgressReporter = reporter or NullReporter()

        if isinstance(raw_input, dict):
            validated_input = self.input_schema().model_validate(raw_input)
        elif isinstance(raw_input, self.input_schema()):
            validated_input = raw_input
        else:
            validated_input = self.input_schema().model_validate(
                raw_input.model_dump()
            )

        self._status = PluginStatus.RUNNING
        try:
            prepared = self.pre_execute(validated_input)
            raw_output = self.execute(prepared, reporter=effective_reporter)
            final = self.post_execute(prepared, raw_output)

            validated_output = self.output_schema().model_validate(
                final.model_dump()
            )

            self._status = PluginStatus.COMPLETED
            return validated_output

        except Exception:
            self._status = PluginStatus.ERROR
            raise

    @property
    def status(self) -> PluginStatus:
        return self._status

    def health_check(self) -> Dict[str, Any]:
        """Quick liveness probe. Override for deeper checks."""
        info = self.get_info()
        return {
            "plugin": info.name,
            "version": info.version,
            "status": self._status.value,
        }

    # ------------------------------------------------------------------
    # Capability declaration
    # ------------------------------------------------------------------
    # Plugins declare *what* they need and *how* they can be reached by
    # setting the class-level fields below or overriding manifest().
    # Defaults assume a small CPU-only in-process plugin (the safe shape
    # — opt into heavier isolation by being explicit). MotionCor would
    # set isolation = IsolationLevel.CONTAINER and resources with
    # gpu_count=1, memory_mb=32_000.

    capabilities: ClassVar[List[Capability]] = []
    supported_transports: ClassVar[List[Transport]] = [Transport.IN_PROCESS]
    default_transport: ClassVar[Transport] = Transport.IN_PROCESS
    isolation: ClassVar[IsolationLevel] = IsolationLevel.IN_PROCESS
    resource_hints: ClassVar[ResourceHints] = ResourceHints()
    replaces: ClassVar[List[str]] = []
    deprecates: ClassVar[List[str]] = []
    tags: ClassVar[List[str]] = []
    backend_id: ClassVar[Optional[str]] = None
    """The plugin's substitutable identity within its category.

    Set this when two plugins in the same category will run side-by-side
    (e.g. ``ctffind4`` vs ``gctf``). When ``None`` the manifest builder
    derives a slug from :meth:`get_info`'s ``name`` so existing plugins
    keep dispatching without a code change."""

    def manifest(self) -> PluginManifest:
        """Build the manifest the host's plugin manager consumes.

        Default builds from the class-level capability fields plus
        :meth:`get_info`. Plugins that need dynamic detection (e.g.
        "GPU_REQUIRED only if CUDA isn't present") may override this and
        compute the capability set at call time.

        Includes JSON Schemas of the input/output contract — generated
        from the Pydantic classes the plugin declares in :meth:`input_schema`
        and :meth:`output_schema`. Hub UIs render forms from these;
        validation layers check submissions against them.
        """
        # Schemas are best-effort: a plugin with an exotic / non-serializable
        # shape shouldn't fail manifest() just because JSON-Schema emit
        # hiccups. Swallow and log; the rest of the manifest is still useful.
        input_schema_json: Optional[dict] = None
        output_schema_json: Optional[dict] = None
        try:
            input_schema_json = self.input_schema().model_json_schema()
        except Exception:  # noqa: BLE001
            logger.debug("input_schema() JSON-Schema emit failed for %s", type(self).__name__)
        try:
            output_schema_json = self.output_schema().model_json_schema()
        except Exception:  # noqa: BLE001
            logger.debug("output_schema() JSON-Schema emit failed for %s", type(self).__name__)

        return PluginManifest(
            info=self.get_info(),
            backend_id=self.backend_id,
            capabilities=list(self.capabilities),
            supported_transports=list(self.supported_transports),
            default_transport=self.default_transport,
            isolation=self.isolation,
            resources=self.resource_hints,
            replaces=list(self.replaces),
            deprecates=list(self.deprecates),
            tags=list(self.tags),
            input_schema=input_schema_json,
            output_schema=output_schema_json,
        )


__all__ = ["InputT", "OutputT", "PluginBase"]

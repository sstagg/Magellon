"""
Base class for all Magellon processing plugins.

Every plugin backend (template picker, deep picker, CTF, etc.) must
subclass ``PluginBase`` and implement all abstract methods.  The host
(controller / job manager / RabbitMQ consumer) interacts with plugins
exclusively through this interface.

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

from models.plugins_models import (
    PluginInfo,
    PluginStatus,
    RequirementResult,
    RecuirementResultEnum,
    TaskCategory,
)

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class PluginBase(ABC, Generic[InputT, OutputT]):
    """
    Strict contract that every Magellon plugin must implement.

    Type parameters
    ---------------
    InputT : BaseModel subclass — validated input for execute()
    OutputT : BaseModel subclass — validated output from execute()
    """

    # -- class-level declarations (override in subclass) -------------------

    task_category: ClassVar[TaskCategory]

    # -- instance state ----------------------------------------------------

    def __init__(self) -> None:
        self._status: PluginStatus = PluginStatus.DISCOVERED
        self._config: Dict[str, Any] = {}

    # -- metadata ----------------------------------------------------------

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

    # -- lifecycle: discovery & installation --------------------------------

    def check_requirements(self) -> List[RequirementResult]:
        """
        Verify that runtime dependencies are available.

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

    # -- lifecycle: configuration ------------------------------------------

    def configure(self, settings: Dict[str, Any] | None = None) -> None:
        """
        Apply external configuration before first use.

        Called once (or on reconfigure).  Store whatever the plugin needs
        in ``self._config``.  Override for custom validation.
        """
        if settings:
            self._config.update(settings)
        self._status = PluginStatus.CONFIGURED

    # -- lifecycle: activation / deactivation -------------------------------

    def setup(self) -> None:
        """
        One-time initialisation after configure().

        Load models into memory, open persistent connections, allocate GPU
        contexts, etc.  Override when your plugin has expensive init.
        """
        self._status = PluginStatus.READY

    def teardown(self) -> None:
        """
        Release resources acquired in setup().

        Close connections, free GPU memory, flush caches, etc.
        """
        self._status = PluginStatus.DISABLED

    # -- lifecycle: execution ----------------------------------------------

    def pre_execute(self, input_data: InputT) -> InputT:
        """
        Hook called before execute().

        Use for logging, enrichment, or input transformation.
        Must return the (possibly modified) input.
        """
        return input_data

    @abstractmethod
    def execute(self, input_data: InputT) -> OutputT:
        """
        Core processing — the only method every plugin *must* implement.
        """
        ...

    def post_execute(self, input_data: InputT, output_data: OutputT) -> OutputT:
        """
        Hook called after execute().

        Use for logging, metrics, or output enrichment.
        Must return the (possibly modified) output.
        """
        return output_data

    # -- public entry point (do not override) ------------------------------

    def run(self, raw_input: Dict[str, Any] | InputT) -> OutputT:
        """
        Validated execution pipeline: validate → pre → execute → post → validate.

        This is the method the host calls.  It enforces the Pydantic
        contracts on both sides and manages status transitions.
        """
        # --- validate input ---
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
            raw_output = self.execute(prepared)
            final = self.post_execute(prepared, raw_output)

            # --- validate output ---
            validated_output = self.output_schema().model_validate(
                final.model_dump()
            )

            self._status = PluginStatus.COMPLETED
            return validated_output

        except Exception:
            self._status = PluginStatus.ERROR
            raise

    # -- introspection -----------------------------------------------------

    @property
    def status(self) -> PluginStatus:
        return self._status

    def health_check(self) -> Dict[str, Any]:
        """Quick liveness probe.  Override for deeper checks."""
        info = self.get_info()
        return {
            "plugin": info.name,
            "version": info.version,
            "status": self._status.value,
        }

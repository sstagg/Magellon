"""CategoryContract: the stable slot every plugin implements.

A category is a *role* the system needs filled — the "what kind of
job". A plugin is *one implementation* of that role. Multiple plugins
can subscribe to the same category; the dispatcher publishes to the
category subject and whichever plugin is free picks the task up.

The contract's job is to make that substitutability real:

  - Canonical ``input_model`` pins the fields every plugin in the
    category must accept. Plugins may accept more via the input
    model's ``engine_opts`` dict (contravariant input).

  - Canonical ``output_model`` pins the fields every plugin in the
    category must produce. Plugins may produce more via ``extras``
    on the output (covariant output).

  - Broker subjects are named deterministically from the category
    code so discovery, heartbeats, and config all follow one rule
    instead of drifting per-plugin.

This module is deliberately free of transport/broker imports — the
subject strings are plain constants. The harness that ties them to
pika/nats lives elsewhere.
"""
from __future__ import annotations

from typing import Dict, Type

from pydantic import BaseModel, ConfigDict

from magellon_sdk.categories.outputs import (
    CategoryOutput,
    CtfOutput,
    FftOutput,
    HoleDetectionOutput,
    MicrographDenoisingOutput,
    MotionCorOutput,
    ParticlePickingOutput,
    SquareDetectionOutput,
)
from magellon_sdk.models.tasks import (
    CTF_TASK,
    CryoEmImageTaskData,
    CryoEmMotionCorTaskData,
    CtfTaskData,
    FFT_TASK,
    FftTaskData,
    HOLE_DETECTION,
    MICROGRAPH_DENOISING,
    MOTIONCOR,
    MicrographDenoiseTaskData,
    PARTICLE_PICKING,
    PtolemyTaskData,
    SQUARE_DETECTION,
    TOPAZ_PARTICLE_PICKING,
    TaskCategory,
    TopazPickTaskData,
)


# ---------------------------------------------------------------------------
# Subject-naming convention
# ---------------------------------------------------------------------------
# All broker subjects derive from one base prefix. Keeping the rule
# here (not sprinkled across plugins) means we can change the prefix
# in one place if we ever need to namespace for multi-tenant.
_PREFIX = "magellon"


def task_subject(category_name: str) -> str:
    """Subject a plugin subscribes to for incoming tasks."""
    return f"{_PREFIX}.tasks.{category_name.lower()}"


def result_subject(category_name: str) -> str:
    """Subject the plugin publishes results on."""
    return f"{_PREFIX}.tasks.{category_name.lower()}.result"


def heartbeat_subject(category_name: str, plugin_name: str) -> str:
    """Per-plugin liveness pulse."""
    return f"{_PREFIX}.plugins.heartbeat.{category_name.lower()}.{plugin_name}"


def announce_subject(category_name: str, plugin_name: str) -> str:
    """One-shot manifest publish at plugin startup."""
    return f"{_PREFIX}.plugins.announce.{category_name.lower()}.{plugin_name}"


def config_subject(category_name: str) -> str:
    """Category-wide config push. All plugins in the category subscribe."""
    return f"{_PREFIX}.plugins.config.{category_name.lower()}"


CONFIG_BROADCAST_SUBJECT = f"{_PREFIX}.plugins.config.broadcast"
"""Global config push — every plugin subscribes regardless of category."""


# ---------------------------------------------------------------------------
# Base input mixin for diversity
# ---------------------------------------------------------------------------

class PluginInputExtras(BaseModel):
    """Mixin for the contravariant-input escape hatch.

    A plugin's input schema may carry more than the category requires
    by populating ``engine_opts`` with plugin-specific knobs. The
    backend treats this field as opaque — it round-trips unchanged.
    """

    engine_opts: Dict[str, object] = {}


# ---------------------------------------------------------------------------
# CategoryContract
# ---------------------------------------------------------------------------

class CategoryContract(BaseModel):
    """The anchor every plugin and dispatcher reads from.

    Instances are constants: one per category. They're pydantic
    models mostly for shape checking and JSON dumping in tests — not
    because they round-trip over the wire.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    category: TaskCategory
    """Existing TaskCategory constant (code + name + description).
    Kept so the contract stays interoperable with ``TaskDto.type``."""

    input_model: Type[BaseModel]
    """Canonical wire input. Plugins may subclass; they must accept
    at least these fields."""

    output_model: Type[CategoryOutput]
    """Canonical output. Plugins must produce at least these fields;
    may populate ``extras`` with more."""

    @property
    def task_subject(self) -> str:
        return task_subject(self.category.name)

    @property
    def result_subject(self) -> str:
        return result_subject(self.category.name)

    @property
    def config_subject(self) -> str:
        return config_subject(self.category.name)

    def heartbeat_subject(self, plugin_name: str) -> str:
        return heartbeat_subject(self.category.name, plugin_name)

    def announce_subject(self, plugin_name: str) -> str:
        return announce_subject(self.category.name, plugin_name)

    def validate_input(self, data: dict) -> BaseModel:
        """Validate a raw task payload against the category's input.

        A plugin that subclasses ``input_model`` can call
        ``self.plugin_input_schema.model_validate(data)`` directly;
        this helper is for generic code paths (dispatcher, tests)
        that only know the category, not the plugin.
        """
        return self.input_model.model_validate(data)


# ---------------------------------------------------------------------------
# Concrete categories
# ---------------------------------------------------------------------------

FFT = CategoryContract(
    category=FFT_TASK,
    input_model=FftTaskData,
    output_model=FftOutput,
)

CTF = CategoryContract(
    category=CTF_TASK,
    input_model=CtfTaskData,
    output_model=CtfOutput,
)

MOTIONCOR_CATEGORY = CategoryContract(
    category=MOTIONCOR,
    input_model=CryoEmMotionCorTaskData,
    output_model=MotionCorOutput,
)

PARTICLE_PICKER = CategoryContract(
    category=PARTICLE_PICKING,
    # Particle picking has no existing SDK input shape — the richer
    # TemplatePickerInput lives in CoreService. The minimum every
    # picker needs is an image to read; richer fields flow through
    # engine_opts. When a canonical PP input model lands in the SDK
    # this pointer updates without touching consumers.
    input_model=CryoEmImageTaskData,
    output_model=ParticlePickingOutput,
)

SQUARE_DETECT = CategoryContract(
    category=SQUARE_DETECTION,
    input_model=PtolemyTaskData,
    output_model=SquareDetectionOutput,
)

HOLE_DETECT = CategoryContract(
    category=HOLE_DETECTION,
    input_model=PtolemyTaskData,
    output_model=HoleDetectionOutput,
)

TOPAZ_PICK = CategoryContract(
    category=TOPAZ_PARTICLE_PICKING,
    input_model=TopazPickTaskData,
    output_model=ParticlePickingOutput,
)

DENOISE = CategoryContract(
    category=MICROGRAPH_DENOISING,
    input_model=MicrographDenoiseTaskData,
    output_model=MicrographDenoisingOutput,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Keyed by TaskCategory.code so the dispatcher can look up the
# contract from the integer code carried on TaskDto.type.

CATEGORIES: Dict[int, CategoryContract] = {
    FFT.category.code: FFT,
    CTF.category.code: CTF,
    MOTIONCOR_CATEGORY.category.code: MOTIONCOR_CATEGORY,
    PARTICLE_PICKER.category.code: PARTICLE_PICKER,
    SQUARE_DETECT.category.code: SQUARE_DETECT,
    HOLE_DETECT.category.code: HOLE_DETECT,
    TOPAZ_PICK.category.code: TOPAZ_PICK,
    DENOISE.category.code: DENOISE,
}


def get_category(code: int) -> CategoryContract:
    """Look up a category contract by TaskCategory code."""
    try:
        return CATEGORIES[code]
    except KeyError:
        raise KeyError(
            f"No CategoryContract registered for task-type code {code}. "
            f"Known codes: {sorted(CATEGORIES.keys())}"
        ) from None


__all__ = [
    "CategoryContract",
    "PluginInputExtras",
    "FFT",
    "CTF",
    "MOTIONCOR_CATEGORY",
    "PARTICLE_PICKER",
    "SQUARE_DETECT",
    "HOLE_DETECT",
    "TOPAZ_PICK",
    "DENOISE",
    "CATEGORIES",
    "CONFIG_BROADCAST_SUBJECT",
    "get_category",
    "task_subject",
    "result_subject",
    "heartbeat_subject",
    "announce_subject",
    "config_subject",
]

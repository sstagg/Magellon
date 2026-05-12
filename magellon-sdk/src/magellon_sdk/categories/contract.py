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

from typing import Any, Dict, List, Mapping, Type

from pydantic import BaseModel, ConfigDict, Field

from magellon_sdk.categories.outputs import (
    CategoryOutput,
    CtfOutput,
    FftOutput,
    HoleDetectionOutput,
    MicrographDenoisingOutput,
    MotionCorOutput,
    ParticleExtractionOutput,
    ParticlePickingOutput,
    SquareDetectionOutput,
    TwoDClassificationOutput,
)
from magellon_sdk.models.tasks import (
    CTF_TASK,
    CryoEmImageInput,
    MotionCorInput,
    CtfInput,
    FFT_TASK,
    FftInput,
    HOLE_DETECTION,
    MICROGRAPH_DENOISING,
    MOTIONCOR,
    MicrographDenoiseInput,
    PARTICLE_EXTRACTION,
    PARTICLE_PICKING,
    ParticleExtractionInput,
    PtolemyInput,
    SQUARE_DETECTION,
    TOPAZ_PARTICLE_PICKING,
    TWO_D_CLASSIFICATION,
    TaskCategory,
    TopazPickInput,
    TwoDClassificationInput,
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


def task_subject_for_backend(category_name: str, backend_id: str) -> str:
    """Subject for backend-pinned dispatch (SDK 1.3+).

    Used as the symbolic route name when a caller pins a task to a
    specific implementation via :attr:`TaskMessage.target_backend`. The
    binder still maps subjects to physical queues; only the symbolic
    name carries the second axis.
    """
    return f"{_PREFIX}.tasks.{category_name.lower()}.{backend_id.lower()}"


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


class CategoryExample(BaseModel):
    """One ready-to-run example for a plugin's input form.

    Inspired by Gradio's ``examples=[...]`` pattern — picking an entry
    pre-fills every form field. Three small fields:

      - ``name`` — short label shown on the example chip ("Default 300 kV").
      - ``description`` — one-line context for the example, surfaced in
        tooltip or detail row ("Standard cryo conditions, K3 detector").
      - ``values`` — dict matching the contract's ``input_model`` shape.
        Validated against the model when the example is registered so
        a broken example fails at category-contract load time, not at
        operator click time.

    The values may reference symbolic paths that don't exist yet
    (e.g. ``/gpfs/templates/...``); the form pre-fills them as-is and
    the operator edits before running. Conservative defaults — every
    example here should be safely executable on the canonical sample
    micrograph the dev stack ships.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    values: Dict[str, Any]


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
    Kept so the contract stays interoperable with ``TaskMessage.type``."""

    input_model: Type[BaseModel]
    """Canonical wire input. Plugins may subclass; they must accept
    at least these fields."""

    output_model: Type[CategoryOutput]
    """Canonical output. Plugins must produce at least these fields;
    may populate ``extras`` with more."""

    subject_kind: str = "image"
    """Phase 3d (2026-05-03). The kind of entity tasks of this
    category operate on. Most categories are image-keyed (CTF,
    MotionCor, FFT, PARTICLE_PICKING, PARTICLE_EXTRACTION) so the
    default is ``'image'``. Aggregate categories override —
    ``TWO_D_CLASSIFICATION`` operates on a ``'particle_stack'``.

    Used by :class:`magellon_sdk.runner.PluginBrokerRunner` as the
    fallback when neither the dispatch (``TaskMessage.subject_kind``)
    nor the plugin (``TaskResultMessage.subject_kind`` from the
    factory) set the field. The DDL default on
    ``image_job_task.subject_kind`` is also ``'image'``, so this
    aligns the in-memory and on-disk defaults."""

    produces_subject_kind: str | None = None
    """PE1-A (2026-05-10). The subject kind of the artifact this
    category emits, when it differs from the input ``subject_kind``.
    ``None`` (the default) means "same as input" — covers in-place
    operations like CTF, MotionCor, FFT. Transforming categories set
    it explicitly: ``PARTICLE_EXTRACTION`` reads images and produces
    particle stacks, so ``produces_subject_kind='particle_stack'``.

    Surfaced on ``GET /plugins/capabilities`` so the catalog UI and
    a future workflow composer can answer "which plugins can consume
    the output of this one?" from capability metadata alone."""

    input_subjects: Mapping[str, str] = {}
    """PE1-B (2026-05-11). Per-field subject tag for inputs. Maps
    input-model field name → subject-kind tag (from the same
    vocabulary as ``subject_kind`` / ``Artifact.kind``:
    ``image | particle_stack | class_averages | session | run | artifact``).

    Empty dict (the default) means "no field-level tags declared" —
    legacy contracts pass dispatch validation unchanged. Populated
    contracts let the dispatcher validate UUID-typed input fields
    against the referenced Artifact's ``kind`` *before* publishing
    a task — closing the "plugin runs, then fails because the input
    was the wrong shape" class of bug for artifact-OID inputs.

    Today only ``particle_stack_id`` carries an artifact OID
    (TwoDClassificationInput); other UUID fields point at Image /
    Session / Job rows which aren't Artifact subtypes. The dispatch
    gate validates only the artifact-kind tags (``particle_stack``,
    ``class_averages``); ``image`` tags are descriptive metadata
    until Image becomes an Artifact subtype."""

    examples: List[CategoryExample] = Field(default_factory=list)
    """Gradio-style ready-to-run examples for the input form.

    Each entry is a ``{name, description, values}`` triplet — picking
    an example pre-fills the React form so a new operator can try the
    plugin with one click. Empty list (the default) keeps the existing
    "type everything yourself" UX.

    Pure metadata — surfaced via ``/plugins/capabilities`` and consumed
    by the test panel / particle-picking drawer. No backend semantics."""

    output_subjects: Mapping[str, str] = {}
    """PE1-B (2026-05-11). Per-field subject tag for outputs. Maps
    output-model field name → subject-kind tag. Same vocabulary as
    ``input_subjects``.

    Used by the catalog UI / workflow composer to answer "which
    output field carries the produced-artifact OID?" — distinguishes
    a scalar summary (``num_particles``) from the artifact reference
    (``particle_stack_id``). Empty dict means no tags declared."""

    @property
    def task_subject(self) -> str:
        return task_subject(self.category.name)

    def task_subject_for_backend(self, backend_id: str) -> str:
        """Backend-pinned subject; see module-level helper for semantics."""
        return task_subject_for_backend(self.category.name, backend_id)

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

# Force forward-reference resolution before instantiating any contract.
# ``from __future__ import annotations`` makes every annotation lazy;
# Pydantic v2 only auto-resolves at the first model_validate(), so
# bare ``CategoryContract(...)`` calls below would otherwise raise
# ``CategoryContract is not fully defined`` when this module is loaded
# in isolation (e.g. ``pytest tests/test_plugin_manager.py`` without
# the rest of the suite touching CategoryContract first). Explicit
# model_rebuild() makes the import order-independent.
CategoryContract.model_rebuild()

# Field-tag populations below: every category tags its image_id input
# as ``"image"`` for catalog discoverability. Artifact-OID input fields
# (today only ``particle_stack_id``) carry the artifact's kind so the
# dispatch gate can validate the referenced row. Output fields carrying
# an artifact OID (filled in by ``TaskOutputProcessor._maybe_write_artifact``
# after the result is projected) are tagged so the UI knows which output
# field is the produced-artifact reference.

FFT = CategoryContract(
    category=FFT_TASK,
    input_model=FftInput,
    output_model=FftOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="Micrograph FFT",
            description="Power spectrum of a single aligned micrograph.",
            values={
                "image_path": "/gpfs/sample-session/sum/example.mrc",
                "target_name": "example_fft.png",
            },
        ),
    ],
)

CTF = CategoryContract(
    category=CTF_TASK,
    input_model=CtfInput,
    output_model=CtfOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="K3 @ 300 kV (default)",
            description="Standard cryo conditions, K3 detector, 1.0 Å/pixel.",
            values={
                "inputFile": "/gpfs/sample-session/sum/example.mrc",
                "pixelSize": 1.0,
                "accelerationVoltage": 300.0,
                "sphericalAberration": 2.70,
                "amplitudeContrast": 0.07,
                "minimumDefocus": 5000.0,
                "maximumDefocus": 50000.0,
                "defocusSearchStep": 100.0,
            },
        ),
        CategoryExample(
            name="Falcon 4 @ 200 kV",
            description="200 kV setup, finer defocus search for higher-res screening.",
            values={
                "inputFile": "/gpfs/sample-session/sum/example.mrc",
                "pixelSize": 0.95,
                "accelerationVoltage": 200.0,
                "sphericalAberration": 2.70,
                "amplitudeContrast": 0.10,
                "minimumDefocus": 3000.0,
                "maximumDefocus": 40000.0,
                "defocusSearchStep": 50.0,
            },
        ),
    ],
)

MOTIONCOR_CATEGORY = CategoryContract(
    category=MOTIONCOR,
    input_model=MotionCorInput,
    output_model=MotionCorOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="K3 movie, 5×5 patches",
            description="Standard K3 frame stack with local-alignment patches.",
            values={
                "inputFile": "/gpfs/sample-session/movies/example.mrc",
                "InMrc": "/gpfs/sample-session/movies/example.mrc",
                "Gain": "/gpfs/sample-session/calibration/gain.mrc",
                "PatchesX": 5,
                "PatchesY": 5,
                "FtBin": 2,
                "FmDose": 1.0,
                "PixSize": 1.0,
                "kV": 300,
            },
        ),
        CategoryExample(
            name="EER super-res",
            description="Falcon 4i EER frames at 2× sampling, single-patch global align.",
            values={
                "inputFile": "/gpfs/sample-session/movies/example.eer",
                "InEer": "/gpfs/sample-session/movies/example.eer",
                "Gain": "/gpfs/sample-session/calibration/gain.mrc",
                "EerSampling": 2,
                "PatchesX": 1,
                "PatchesY": 1,
                "FmDose": 0.6,
                "PixSize": 0.95,
                "kV": 200,
            },
        ),
    ],
)

PARTICLE_PICKER = CategoryContract(
    category=PARTICLE_PICKING,
    # Particle picking has no existing SDK input shape — the richer
    # TemplatePickerInput lives in CoreService. The minimum every
    # picker needs is an image to read; richer fields flow through
    # engine_opts. When a canonical PP input model lands in the SDK
    # this pointer updates without touching consumers.
    input_model=CryoEmImageInput,
    output_model=ParticlePickingOutput,
    input_subjects={"image_id": "image"},
)

SQUARE_DETECT = CategoryContract(
    category=SQUARE_DETECTION,
    input_model=PtolemyInput,
    output_model=SquareDetectionOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="Low-mag overview",
            description="Detect grid squares on a low-magnification atlas.",
            values={"input_file": "/gpfs/sample-session/atlas/lowmag.mrc"},
        ),
    ],
)

HOLE_DETECT = CategoryContract(
    category=HOLE_DETECTION,
    input_model=PtolemyInput,
    output_model=HoleDetectionOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="Medium-mag square",
            description="Detect foil holes inside one grid square.",
            values={"input_file": "/gpfs/sample-session/atlas/medmag.mrc"},
        ),
    ],
)

TOPAZ_PICK = CategoryContract(
    category=TOPAZ_PARTICLE_PICKING,
    input_model=TopazPickInput,
    output_model=ParticlePickingOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="Topaz default (resnet16)",
            description="Standard Topaz pick with the tutorial defaults.",
            values={
                "input_file": "/gpfs/sample-session/sum/example.mrc",
                "engine_opts": {
                    "model": "resnet16",
                    "radius": 14,
                    "threshold": -3,
                    "scale": 8,
                },
            },
        ),
    ],
)

DENOISE = CategoryContract(
    category=MICROGRAPH_DENOISING,
    input_model=MicrographDenoiseInput,
    output_model=MicrographDenoisingOutput,
    input_subjects={"image_id": "image"},
    examples=[
        CategoryExample(
            name="Topaz-Denoise default",
            description="Single MRC denoised with the default Topaz UNet model.",
            values={"input_file": "/gpfs/sample-session/sum/example.mrc"},
        ),
    ],
)

PARTICLE_EXTRACTION_CATEGORY = CategoryContract(
    category=PARTICLE_EXTRACTION,
    input_model=ParticleExtractionInput,
    output_model=ParticleExtractionOutput,
    # Reads per-image picks; emits a particle stack artifact. This is
    # the canonical "transforming" category — input subject differs
    # from output subject.
    produces_subject_kind="particle_stack",
    input_subjects={"image_id": "image"},
    # ``particle_stack_id`` on the output is filled in by the projector
    # after it writes the Artifact row; tagging it lets the UI surface
    # "this is the produced-artifact reference" without parsing the schema.
    output_subjects={"particle_stack_id": "particle_stack"},
    examples=[
        CategoryExample(
            name="256 px box, 1.0 Å",
            description="Standard ribosome-class boxing — 256 px box at the K3 pixel size.",
            values={
                "micrograph_path": "/gpfs/sample-session/sum/example.mrc",
                "particles_path": "/gpfs/sample-session/picks/example.star",
                "box_size": 256,
                "edge_width": 2,
                "apix": 1.0,
            },
        ),
    ],
)

TWO_D_CLASSIFICATION_CATEGORY = CategoryContract(
    category=TWO_D_CLASSIFICATION,
    input_model=TwoDClassificationInput,
    output_model=TwoDClassificationOutput,
    # 2D classification operates on a particle stack (an aggregate),
    # not a single image. Per ratified rule 7 (one task per stack).
    subject_kind="particle_stack",
    # The only artifact-OID input today — dispatch gate will validate
    # the referenced Artifact's ``kind == "particle_stack"`` before
    # publishing the task. ``image_id`` may also be set (the runner
    # back-compat path) and is descriptively tagged.
    input_subjects={
        "particle_stack_id": "particle_stack",
        "image_id": "image",
    },
    # ``source_particle_stack_id`` echoes the input artifact OID; the
    # produced class-averages OID is stamped onto a separate Artifact
    # row by the projector, not on this output struct.
    output_subjects={"source_particle_stack_id": "particle_stack"},
    examples=[
        CategoryExample(
            name="50 classes, GPU auto",
            description="Standard 2D classification run on a typical particle stack.",
            values={
                "mrcs_path": "/gpfs/sample-session/particles/stack.mrcs",
                "star_path": "/gpfs/sample-session/particles/stack.star",
                "output_dir": "/gpfs/sample-session/class2d",
                "num_classes": 50,
                "num_presentations": 200000,
                "compute_backend": "torch-auto",
            },
        ),
        CategoryExample(
            name="Quick test, 10 classes",
            description="Tiny preview run — 10 classes, CPU-friendly presentations.",
            values={
                "mrcs_path": "/gpfs/sample-session/particles/stack.mrcs",
                "star_path": "/gpfs/sample-session/particles/stack.star",
                "output_dir": "/gpfs/sample-session/class2d_quick",
                "num_classes": 10,
                "num_presentations": 20000,
                "compute_backend": "torch-cpu",
            },
        ),
    ],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Keyed by TaskCategory.code so the dispatcher can look up the
# contract from the integer code carried on TaskMessage.type.

CATEGORIES: Dict[int, CategoryContract] = {
    FFT.category.code: FFT,
    CTF.category.code: CTF,
    MOTIONCOR_CATEGORY.category.code: MOTIONCOR_CATEGORY,
    PARTICLE_PICKER.category.code: PARTICLE_PICKER,
    SQUARE_DETECT.category.code: SQUARE_DETECT,
    HOLE_DETECT.category.code: HOLE_DETECT,
    TOPAZ_PICK.category.code: TOPAZ_PICK,
    DENOISE.category.code: DENOISE,
    PARTICLE_EXTRACTION_CATEGORY.category.code: PARTICLE_EXTRACTION_CATEGORY,
    TWO_D_CLASSIFICATION_CATEGORY.category.code: TWO_D_CLASSIFICATION_CATEGORY,
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
    "PARTICLE_EXTRACTION_CATEGORY",
    "TWO_D_CLASSIFICATION_CATEGORY",
    "CATEGORIES",
    "CONFIG_BROADCAST_SUBJECT",
    "get_category",
    "task_subject",
    "task_subject_for_backend",
    "result_subject",
    "heartbeat_subject",
    "announce_subject",
    "config_subject",
]

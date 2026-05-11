"""Unit tests for ``magellon_sdk.categories``.

These pin the substitutability contract:

  - Every registered category has a canonical input + output model.
  - Subject-naming is derived deterministically from the category
    name (no per-plugin strings leaking in).
  - The I/O diversity rules actually work: plugins can add engine
    options on input, extras on output, without breaking validation
    against the category's canonical model.
"""
from __future__ import annotations

from typing import Optional

import pytest
from pydantic import BaseModel

from magellon_sdk.categories import (
    CATEGORIES,
    CONFIG_BROADCAST_SUBJECT,
    CTF,
    CategoryContract,
    CategoryOutput,
    CtfOutput,
    FFT,
    FftOutput,
    MOTIONCOR_CATEGORY,
    MotionCorOutput,
    PARTICLE_EXTRACTION_CATEGORY,
    PARTICLE_PICKER,
    ParticlePickingOutput,
    TWO_D_CLASSIFICATION_CATEGORY,
    announce_subject,
    config_subject,
    get_category,
    heartbeat_subject,
    result_subject,
    task_subject,
)
from magellon_sdk.models.tasks import (
    CTF_TASK,
    CtfInput,
    FFT_TASK,
    FftInput,
    MOTIONCOR,
    PARTICLE_PICKING,
)


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------

def test_registry_contains_every_known_category():
    """Every TaskCategory the backend can route to must have a contract.
    If this fails because a new category is added, the fix is to register
    it in contract.py — not to weaken the assertion."""
    known_codes = {FFT_TASK.code, CTF_TASK.code, MOTIONCOR.code, PARTICLE_PICKING.code}
    assert known_codes.issubset(CATEGORIES.keys())


def test_get_category_looks_up_by_code():
    assert get_category(CTF_TASK.code) is CTF
    assert get_category(FFT_TASK.code) is FFT


def test_get_category_raises_on_unknown_code():
    with pytest.raises(KeyError, match="No CategoryContract registered"):
        get_category(999_999)


# ---------------------------------------------------------------------------
# Subject naming
# ---------------------------------------------------------------------------

def test_subject_helpers_use_consistent_prefix_and_lowercase():
    """The prefix + lowercased category rule is what dispatchers and
    plugins rely on. Breaking it silently would strand one side on
    the old subject — hence pinning it here."""
    assert task_subject("CTF") == "magellon.tasks.ctf"
    assert result_subject("CTF") == "magellon.tasks.ctf.result"
    assert heartbeat_subject("CTF", "ctffind") == "magellon.plugins.heartbeat.ctf.ctffind"
    assert announce_subject("CTF", "ctffind") == "magellon.plugins.announce.ctf.ctffind"
    assert config_subject("CTF") == "magellon.plugins.config.ctf"


def test_contract_subject_properties_match_helpers():
    assert CTF.task_subject == task_subject(CTF.category.name)
    assert CTF.result_subject == result_subject(CTF.category.name)
    assert CTF.heartbeat_subject("gctf") == heartbeat_subject("CTF", "gctf")
    assert CTF.announce_subject("gctf") == announce_subject("CTF", "gctf")
    assert CTF.config_subject == config_subject(CTF.category.name)


def test_config_broadcast_subject_is_category_agnostic():
    """Global-config pushes don't name any category — plugins of every
    category subscribe to the same subject for things like GPFS root."""
    assert CONFIG_BROADCAST_SUBJECT == "magellon.plugins.config.broadcast"


# ---------------------------------------------------------------------------
# Canonical input/output wiring
# ---------------------------------------------------------------------------

def test_each_category_points_at_its_canonical_models():
    assert CTF.input_model is CtfInput
    assert CTF.output_model is CtfOutput
    assert FFT.input_model is FftInput
    assert FFT.output_model is FftOutput
    assert MOTIONCOR_CATEGORY.output_model is MotionCorOutput
    assert PARTICLE_PICKER.output_model is ParticlePickingOutput


def test_validate_input_accepts_canonical_payload():
    """A dispatcher that only knows the category code can still
    validate a task's data without importing plugin-specific types."""
    payload = {
        "image_path": "/gpfs/images/mic_0001.mrc",
        "inputFile": "/gpfs/images/mic_0001.mrc",
    }
    obj = CTF.validate_input(payload)
    assert isinstance(obj, CtfInput)
    assert obj.inputFile == "/gpfs/images/mic_0001.mrc"


# ---------------------------------------------------------------------------
# Diversity: contravariant input
# ---------------------------------------------------------------------------

def test_input_accepts_engine_opts_as_opaque_extras():
    """The whole point of engine_opts: a plugin can carry its own
    knobs through the canonical schema without forcing the category
    to know about them. An old dispatcher that doesn't populate
    engine_opts must still produce a valid input."""
    # Without engine_opts — default empty.
    bare = CtfInput(inputFile="/gpfs/x.mrc")
    assert bare.engine_opts == {}

    # With engine-specific knobs — gctf wants a gpu_id.
    extended = CtfInput(
        inputFile="/gpfs/x.mrc",
        engine_opts={"gpu_id": 1, "window_size": 512},
    )
    assert extended.engine_opts["gpu_id"] == 1

    # Round-trip preserves engine_opts.
    round_tripped = CtfInput.model_validate(extended.model_dump())
    assert round_tripped.engine_opts == {"gpu_id": 1, "window_size": 512}


def test_plugin_subclassing_input_preserves_canonical_fields():
    """A plugin that wants richer input (typed, not just dict) can
    subclass the canonical model. The category's validator still
    works because the plugin's type is-a canonical type."""

    class GctfInput(CtfInput):
        # Strongly-typed alternative to engine_opts["gpu_id"].
        gpu_id: int = 0

    payload = {
        "image_path": "/gpfs/x.mrc",
        "inputFile": "/gpfs/x.mrc",
        "gpu_id": 3,
    }
    # Plugin-specific validation keeps the extra field.
    plugin_view = GctfInput.model_validate(payload)
    assert plugin_view.gpu_id == 3

    # Category-level validation accepts the same payload — extras
    # are silently ignored (they're declared on the subclass, not
    # the canonical model).
    canonical_view = CTF.validate_input(payload)
    assert canonical_view.inputFile == "/gpfs/x.mrc"
    assert not hasattr(canonical_view, "gpu_id") or canonical_view.model_extra is None


# ---------------------------------------------------------------------------
# Diversity: covariant output
# ---------------------------------------------------------------------------

def test_output_base_has_extras_field():
    """Every category output inherits extras so plugin-specific
    fields have a home that generic consumers (the DB projector)
    can safely ignore."""
    out = CtfOutput(
        defocus_u=10_000.0,
        defocus_v=10_100.0,
        astigmatism_angle=12.0,
        cc=0.8,
        resolution_limit=3.5,
    )
    assert out.extras == {}
    assert isinstance(out, CategoryOutput)


def test_plugin_output_extras_preserve_extra_fields():
    """A richer plugin populates extras; projection round-trips them."""
    out = CtfOutput(
        defocus_u=10_000.0,
        defocus_v=10_100.0,
        astigmatism_angle=12.0,
        cc=0.8,
        resolution_limit=3.5,
        extras={"per_tile_variance": [0.1, 0.2, 0.3], "engine_version": "gctf-2.1"},
    )

    dumped = out.model_dump()
    restored = CtfOutput.model_validate(dumped)
    assert restored.extras["per_tile_variance"] == [0.1, 0.2, 0.3]
    assert restored.extras["engine_version"] == "gctf-2.1"


def test_plugin_subclassing_output_is_still_a_category_output():
    """A plugin with typed extras (subclass) must still look like a
    CategoryOutput to anyone holding the canonical type — same Liskov
    rule the input side enforces."""

    class GctfOutput(CtfOutput):
        per_tile_variance: list[float] = []

    rich = GctfOutput(
        defocus_u=10_000.0, defocus_v=10_100.0, astigmatism_angle=12.0,
        cc=0.8, resolution_limit=3.5,
        per_tile_variance=[0.1, 0.2],
    )
    assert isinstance(rich, CtfOutput)
    assert isinstance(rich, CategoryOutput)
    # The category's projection reads only the declared fields.
    canonical = CtfOutput.model_validate(rich.model_dump())
    assert canonical.defocus_u == 10_000.0


# ---------------------------------------------------------------------------
# Contract is immutable
# ---------------------------------------------------------------------------

def test_contract_is_frozen():
    """Contracts are constants — a plugin mutating one at runtime
    would be a nasty bug. Pin that frozen=True stays on."""
    with pytest.raises(Exception):  # pydantic raises ValidationError on frozen
        CTF.category = FFT_TASK  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PE1-B: per-field subject tags
# ---------------------------------------------------------------------------

_ARTIFACT_KIND_VOCAB = {
    "image",
    "particle_stack",
    "class_averages",
    "session",
    "run",
    "artifact",
}
"""The shared subject-kind vocabulary (Artifact.kind ∪ subject_kind).
Any tag PE1-B contracts use must come from this set. Growing the
vocab is fine — but it should grow in lockstep with new Artifact
subtypes, not drift independently per category."""


def test_field_subjects_default_empty_for_legacy_contracts():
    """A contract that doesn't declare any field tags is legal —
    legacy categories pass dispatch validation unchanged. New
    categories opt in by populating the maps."""
    legacy = CategoryContract(
        category=CTF_TASK,
        input_model=CtfInput,
        output_model=CtfOutput,
    )
    assert legacy.input_subjects == {}
    assert legacy.output_subjects == {}


def test_every_contract_field_tag_uses_known_vocab():
    """Typo guard: a contract declaring ``input_subjects={"foo": "MicroGrap"}``
    would silently never match a real Artifact.kind. Reject anything
    outside the agreed vocab at test time so the typo surfaces here
    instead of as a mysterious dispatch-gate miss in production."""
    for code, contract in CATEGORIES.items():
        for field, tag in contract.input_subjects.items():
            assert tag in _ARTIFACT_KIND_VOCAB, (
                f"Category {contract.category.name} input field "
                f"{field!r} uses unknown subject tag {tag!r}; "
                f"vocabulary is {sorted(_ARTIFACT_KIND_VOCAB)}"
            )
        for field, tag in contract.output_subjects.items():
            assert tag in _ARTIFACT_KIND_VOCAB, (
                f"Category {contract.category.name} output field "
                f"{field!r} uses unknown subject tag {tag!r}; "
                f"vocabulary is {sorted(_ARTIFACT_KIND_VOCAB)}"
            )


def test_two_d_classification_tags_particle_stack_id_as_artifact_input():
    """The dispatch gate's primary target: ``particle_stack_id`` is the
    one artifact-OID input field in the system today. If this tag goes
    missing, the gate silently stops validating 2D-class dispatches."""
    assert (
        TWO_D_CLASSIFICATION_CATEGORY.input_subjects.get("particle_stack_id")
        == "particle_stack"
    )


def test_particle_extraction_tags_output_artifact_id():
    """The extractor's output carries the produced particle_stack OID
    (filled in by the projector). Tagging it lets the catalog UI
    surface "this is the produced-artifact reference field" without
    parsing the JSON Schema."""
    assert (
        PARTICLE_EXTRACTION_CATEGORY.output_subjects.get("particle_stack_id")
        == "particle_stack"
    )


def test_image_keyed_categories_tag_image_id():
    """Every image-keyed category tags ``image_id``. Descriptive today
    (the Image table isn't an Artifact subtype, so dispatch doesn't
    validate against it); becomes load-bearing if Image migrates to
    Artifact STI."""
    image_keyed = [
        FFT, CTF, MOTIONCOR_CATEGORY, PARTICLE_PICKER, PARTICLE_EXTRACTION_CATEGORY,
    ]
    for contract in image_keyed:
        assert contract.input_subjects.get("image_id") == "image", (
            f"{contract.category.name} should tag image_id as 'image'"
        )

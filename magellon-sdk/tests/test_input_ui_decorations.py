"""Smoke tests for the ui_* JSON-Schema decorations on plugin inputs.

The React ``SchemaForm`` discovers widget hints by reading
``json_schema_extra`` on each Pydantic Field. Without these decorations
the form falls back to bare TextField/Checkbox controls — every plugin
ends up looking the same. These tests pin:

  - Each canonical input model declares ``ui_widget`` (or ``ui_hidden``)
    for every public field — no "bare" fields slipped through.
  - Key sliders / numbers carry the units / marks operators expect to
    see in the rendered form.
  - The ``ui_tunable`` flag is set on the parameters where the
    preview/retune flow needs it (CTF defocus search, MotionCor
    patches, 2D classification num_classes).
  - JSON-Schema generation still succeeds (no Pydantic error from a
    malformed ``json_schema_extra``).
"""
from __future__ import annotations

from typing import Iterable

import pytest
from pydantic import BaseModel

from magellon_sdk.models.tasks import (
    CtfInput,
    FftInput,
    MicrographDenoiseInput,
    MotionCorInput,
    ParticleExtractionInput,
    PtolemyInput,
    TopazPickInput,
    TwoDClassificationInput,
)


DECORATED_MODELS: list[type[BaseModel]] = [
    CtfInput,
    FftInput,
    MotionCorInput,
    TopazPickInput,
    MicrographDenoiseInput,
    PtolemyInput,
    ParticleExtractionInput,
    TwoDClassificationInput,
]


# Fields inherited from CryoEmImageInput are deliberately undecorated —
# the React side either hides them (image_id is auto-supplied) or shows
# them via the fallback text renderer. Don't fail the smoke test on
# inherited base fields.
INHERITED_BASE_FIELDS = {"image_id", "image_name", "image_path", "engine_opts"}


def _field_ui_keys(schema: dict, field_name: str) -> dict:
    """Pull the ``ui_*`` and other metadata keys off a field's schema."""
    props = schema.get("properties", {})
    return props.get(field_name, {})


# ---------------------------------------------------------------------------
# Smoke: every decorated model still produces a valid JSON schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", DECORATED_MODELS, ids=lambda m: m.__name__)
def test_model_json_schema_still_serialises(model):
    """A malformed json_schema_extra dict would crash here. This is the
    cheapest regression net — every decorated model must round-trip."""
    schema = model.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema


# ---------------------------------------------------------------------------
# Every own (non-inherited) field declares a widget or ui_hidden
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", DECORATED_MODELS, ids=lambda m: m.__name__)
def test_own_fields_have_ui_widget_or_hidden(model):
    """A field with no ``ui_widget`` AND no ``ui_hidden`` ends up using
    the type-driven fallback renderer. That's fine for legacy plugins —
    but for the canonical SDK inputs we want every field decorated so
    the rendered form has consistent groups, units, and help text.
    """
    schema = model.model_json_schema()
    own_fields = [
        f for f in model.model_fields
        if f not in INHERITED_BASE_FIELDS
    ]
    undecorated: list[str] = []
    for name in own_fields:
        meta = _field_ui_keys(schema, name)
        if not meta.get("ui_widget") and not meta.get("ui_hidden"):
            undecorated.append(name)

    assert not undecorated, (
        f"{model.__name__} fields lack ui_widget / ui_hidden: {undecorated}. "
        f"Decorate via ``Field(..., json_schema_extra={{...}})``."
    )


# ---------------------------------------------------------------------------
# Spot-checks on specific decorations operators care about
# ---------------------------------------------------------------------------


class TestCtfDecorations:
    def test_pixel_size_has_unit(self):
        schema = CtfInput.model_json_schema()
        assert _field_ui_keys(schema, "pixelSize")["ui_unit"] == "Å"

    def test_voltage_is_select(self):
        schema = CtfInput.model_json_schema()
        meta = _field_ui_keys(schema, "accelerationVoltage")
        assert meta["ui_widget"] == "select"
        assert 300.0 in meta["ui_options"]

    def test_defocus_search_step_is_tunable_slider(self):
        schema = CtfInput.model_json_schema()
        meta = _field_ui_keys(schema, "defocusSearchStep")
        assert meta["ui_widget"] == "slider"
        assert meta["ui_tunable"] is True
        assert meta["ui_marks"]

    def test_advanced_fields_collapsed(self):
        schema = CtfInput.model_json_schema()
        for advanced in ("sphericalAberration", "amplitudeContrast", "binning_x"):
            meta = _field_ui_keys(schema, advanced)
            assert meta.get("ui_advanced") is True, (
                f"{advanced} should be under Advanced"
            )


class TestMotionCorDecorations:
    def test_patches_are_tunable_sliders(self):
        schema = MotionCorInput.model_json_schema()
        for fld in ("PatchesX", "PatchesY"):
            meta = _field_ui_keys(schema, fld)
            assert meta["ui_widget"] == "slider"
            assert meta["ui_tunable"] is True

    def test_input_files_grouped_under_frames(self):
        schema = MotionCorInput.model_json_schema()
        for fld in ("InMrc", "InTiff", "InEer"):
            meta = _field_ui_keys(schema, fld)
            assert meta["ui_group"] == "Frames"

    def test_inputFile_is_hidden(self):
        schema = MotionCorInput.model_json_schema()
        meta = _field_ui_keys(schema, "inputFile")
        assert meta.get("ui_widget") == "hidden"


class TestTwoDClassificationDecorations:
    def test_num_classes_is_tunable_slider(self):
        schema = TwoDClassificationInput.model_json_schema()
        meta = _field_ui_keys(schema, "num_classes")
        assert meta["ui_widget"] == "slider"
        assert meta["ui_tunable"] is True

    def test_compute_backend_options_cover_torch_variants(self):
        schema = TwoDClassificationInput.model_json_schema()
        meta = _field_ui_keys(schema, "compute_backend")
        assert "torch-cuda" in meta["ui_options"]
        assert "torch-mps" in meta["ui_options"]

    def test_particle_stack_id_hidden_from_form(self):
        schema = TwoDClassificationInput.model_json_schema()
        meta = _field_ui_keys(schema, "particle_stack_id")
        assert meta.get("ui_widget") == "hidden"


# ---------------------------------------------------------------------------
# File-path fields carry an extension allowlist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model,field,expected_ext", [
    (CtfInput, "inputFile", ".mrc"),
    (MotionCorInput, "InMrc", ".mrc"),
    (MotionCorInput, "InTiff", ".tif"),
    (MotionCorInput, "InEer", ".eer"),
    (MicrographDenoiseInput, "input_file", ".mrc"),
    (TopazPickInput, "input_file", ".mrc"),
    (PtolemyInput, "input_file", ".mrc"),
    (ParticleExtractionInput, "micrograph_path", ".mrc"),
    (TwoDClassificationInput, "mrcs_path", ".mrcs"),
    (TwoDClassificationInput, "star_path", ".star"),
])
def test_file_path_field_advertises_extension(model, field, expected_ext):
    schema = model.model_json_schema()
    meta = _field_ui_keys(schema, field)
    assert meta["ui_widget"] == "file_path"
    exts = meta.get("ui_file_ext", [])
    assert expected_ext in exts, (
        f"{model.__name__}.{field} expected to allow {expected_ext}, got {exts}"
    )

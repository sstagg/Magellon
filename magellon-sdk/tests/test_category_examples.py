"""Smoke tests for ``CategoryContract.examples``.

The Gradio-style examples on each contract are pure metadata — picked
up by ``GET /plugins/capabilities`` and rendered as "Try example" chips
in the React test panel. These tests pin:

  - Every published example validates against its category's input
    model. A typo in an example would otherwise surface only when an
    operator clicks it.
  - Examples carry a non-empty name (used as the chip label).
  - Categories where examples matter most (CTF, MotionCor,
    PARTICLE_EXTRACTION, TWO_D_CLASSIFICATION) ship at least one.
"""
from __future__ import annotations

import pytest

from magellon_sdk.categories import (
    CATEGORIES,
    CTF,
    DENOISE,
    FFT,
    HOLE_DETECT,
    MOTIONCOR_CATEGORY,
    PARTICLE_EXTRACTION_CATEGORY,
    SQUARE_DETECT,
    TOPAZ_PICK,
    TWO_D_CLASSIFICATION_CATEGORY,
)


CATEGORIES_WITH_REQUIRED_EXAMPLES = [
    CTF,
    MOTIONCOR_CATEGORY,
    PARTICLE_EXTRACTION_CATEGORY,
    TWO_D_CLASSIFICATION_CATEGORY,
    FFT,
    TOPAZ_PICK,
    DENOISE,
    SQUARE_DETECT,
    HOLE_DETECT,
]


# ---------------------------------------------------------------------------
# Every published example validates against its input model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contract",
    list(CATEGORIES.values()),
    ids=lambda c: c.category.name,
)
def test_examples_validate_against_input_model(contract):
    """Without this test, a typo like ``pixelSize: "1.0"`` (string vs
    float) would only surface when an operator clicked the chip and
    the dispatch gate rejected the input."""
    for example in contract.examples:
        try:
            contract.input_model.model_validate(example.values)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"{contract.category.name} example {example.name!r} fails to "
                f"validate against {contract.input_model.__name__}: {exc}",
            )


# ---------------------------------------------------------------------------
# Names are non-empty and unique within a category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contract",
    list(CATEGORIES.values()),
    ids=lambda c: c.category.name,
)
def test_example_names_are_unique_and_nonempty(contract):
    names = [ex.name for ex in contract.examples]
    assert all(n.strip() for n in names), (
        f"{contract.category.name} has an empty example name"
    )
    assert len(names) == len(set(names)), (
        f"{contract.category.name} has duplicate example names: {names}"
    )


# ---------------------------------------------------------------------------
# Categories that the React UI surfaces front-and-centre ship at least one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contract",
    CATEGORIES_WITH_REQUIRED_EXAMPLES,
    ids=lambda c: c.category.name,
)
def test_required_categories_have_examples(contract):
    """Categories operators most often run from the test panel should
    have at least one ready-to-go example so first-touch is friction-free."""
    assert contract.examples, (
        f"{contract.category.name} should ship at least one example"
    )

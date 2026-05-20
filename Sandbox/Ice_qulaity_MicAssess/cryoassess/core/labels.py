"""MicAssess quality labels and threshold-based label assignment."""

from __future__ import annotations

from typing import Sequence

import numpy as np

# The six MicAssess quality classes.  Index order is meaningful: it matches the
# example folders, the output sub-directories, and the model's bad-class head.
LABEL_LIST = (
    "0Great",
    "1Decent",
    "2Contamination_Aggregate_Crack_Breaking_Drifting",
    "3Empty_no_ice",
    "4Crystalline_ice",
    "5Empty_ice_no_particles_but_vitreous_ice",
)

GREAT_LABEL = 0
DECENT_LABEL = 1
GOOD_LABELS = (GREAT_LABEL, DECENT_LABEL)
FIRST_BAD_LABEL = 2

DEFAULT_T1 = 0.1  # good/bad tolerance
DEFAULT_T2 = 0.1  # great/decent tolerance


def assign_label(
    binary_prob: Sequence[float],
    good_prob: Sequence[float],
    bad_prob: Sequence[float],
    t1: float = DEFAULT_T1,
    t2: float = DEFAULT_T2,
) -> int:
    """Return the six-class label for one micrograph from the three model heads.

    ``binary_prob[0]`` is the model's "bad" probability and ``good_prob[0]`` the
    "decent" probability; ``bad_prob`` is the four-way bad-class distribution.
    ``t1``/``t2`` are raw tolerances: a larger ``t1`` pushes more micrographs to
    "bad", a larger ``t2`` pushes more "great" micrographs down to "decent".
    """

    good_cut = 1.0 - t1
    great_cut = 1.0 - t2
    if binary_prob[0] <= good_cut:
        return GREAT_LABEL if good_prob[0] < great_cut else DECENT_LABEL
    return int(np.argmax(bad_prob)) + FIRST_BAD_LABEL


def assign_labels(
    binary_probs: np.ndarray,
    good_probs: np.ndarray,
    bad_probs: np.ndarray,
    t1: float = DEFAULT_T1,
    t2: float = DEFAULT_T2,
) -> np.ndarray:
    """Vectorised :func:`assign_label` over a batch; returns an ``int`` array."""

    return np.array(
        [
            assign_label(binary_probs[i], good_probs[i], bad_probs[i], t1, t2)
            for i in range(len(binary_probs))
        ],
        dtype=int,
    )


def is_good(label: int) -> bool:
    """True if ``label`` is one of the two "good" classes (Great or Decent)."""

    return label in GOOD_LABELS

"""Microscope-facing autofocus orchestration without microscope dependencies.

The protocols in this module describe the small instrument surface needed by
the pure focus pipeline.  Real Magellon microscope adapters can implement these
methods, while tests can use simple fakes.
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, Sequence, Tuple

import numpy as np

from .focus_pipeline import (
    BeamTiltImagePair,
    ObjectiveCalibration,
    StageTiltImagePair,
    solve_objective_focus_from_image_pairs,
    solve_stage_z_from_image_pairs,
)
from .objective_focus import ObjectiveFocusResult
from .z_focus import StageZResult


Vector2 = Tuple[float, float]


class ObjectiveFocusInstrument(Protocol):
    """Minimal beam-tilt/image interface for objective autofocus."""

    def get_beam_tilt(self) -> Vector2:
        ...

    def set_beam_tilt(self, tilt: Vector2) -> None:
        ...

    def acquire_image(self) -> np.ndarray:
        ...


class StageZInstrument(Protocol):
    """Minimal stage-alpha/image interface for stage-tilt Z focus."""

    def get_stage_alpha(self) -> float:
        ...

    def set_stage_alpha(self, alpha: float) -> None:
        ...

    def acquire_image(self) -> np.ndarray:
        ...


def run_objective_focus_sequence(
    instrument: ObjectiveFocusInstrument,
    calibration: ObjectiveCalibration,
    tilt_pairs: Sequence[Tuple[Vector2, Vector2]],
    *,
    apply_correction: Optional[Callable[[ObjectiveFocusResult], None]] = None,
    **pipeline_kwargs,
) -> ObjectiveFocusResult:
    """Acquire beam-tilt image pairs, solve objective focus, and restore beam tilt."""

    if not tilt_pairs:
        raise ValueError("at least one beam-tilt pair is required")

    original_tilt = instrument.get_beam_tilt()
    try:
        image_pairs = []
        for first_tilt, second_tilt in tilt_pairs:
            instrument.set_beam_tilt(first_tilt)
            first_image = instrument.acquire_image()
            instrument.set_beam_tilt(second_tilt)
            second_image = instrument.acquire_image()
            image_pairs.append(
                BeamTiltImagePair(
                    first_tilt=first_tilt,
                    second_tilt=second_tilt,
                    first_image=first_image,
                    second_image=second_image,
                )
            )

        result = solve_objective_focus_from_image_pairs(
            calibration,
            image_pairs,
            **pipeline_kwargs,
        )
        if apply_correction is not None:
            apply_correction(result)
        return result
    finally:
        instrument.set_beam_tilt(original_tilt)


def run_stage_z_sequence(
    instrument: StageZInstrument,
    stage_matrix: np.ndarray,
    alphas: Sequence[float],
    *,
    apply_z_correction: Optional[Callable[[StageZResult], None]] = None,
    zero_alpha: float = 0.0,
    **pipeline_kwargs,
) -> StageZResult:
    """Acquire reference/tilted alpha images, solve Z, and restore stage alpha."""

    if not alphas:
        raise ValueError("at least one stage alpha is required")

    original_alpha = instrument.get_stage_alpha()
    try:
        image_pairs = []
        for alpha in alphas:
            instrument.set_stage_alpha(zero_alpha)
            reference = instrument.acquire_image()
            instrument.set_stage_alpha(alpha)
            tilted = instrument.acquire_image()
            image_pairs.append(
                StageTiltImagePair(
                    alpha=alpha,
                    reference_image=reference,
                    tilted_image=tilted,
                )
            )

        result = solve_stage_z_from_image_pairs(
            stage_matrix,
            image_pairs,
            **pipeline_kwargs,
        )
        if apply_z_correction is not None:
            apply_z_correction(result)
        return result
    finally:
        instrument.set_stage_alpha(original_alpha)


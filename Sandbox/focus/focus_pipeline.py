"""Pure data-flow helpers for autofocus measurements.

These functions intentionally do not move a microscope or retrieve calibration
records.  They connect image correlation to the calibrated numerical solvers so
the microscope-facing layer can stay small and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from .correlation import CorrelationType, ShiftResult, correlate_shift
from .objective_focus import BeamTiltMeasurement, solve_defocus_stig
from .z_focus import StageTiltMeasurement, solve_stage_z


Vector2 = Tuple[float, float]


@dataclass(frozen=True)
class ObjectiveCalibration:
    """Calibration matrices for Leginon-compatible objective autofocus."""

    defocus_matrix: np.ndarray
    stigx_matrix: Optional[np.ndarray] = None
    stigy_matrix: Optional[np.ndarray] = None


@dataclass(frozen=True)
class BeamTiltImagePair:
    """Two images acquired at known beam tilts.

    ``first_image`` and ``second_image`` are correlated as a displacement of the
    second image relative to the first image, matching Leginon's
    ``measureScopeChange`` usage.
    """

    first_tilt: Vector2
    second_tilt: Vector2
    first_image: np.ndarray
    second_image: np.ndarray


@dataclass(frozen=True)
class BeamTiltTripleShot:
    """Three images for one drift-corrected beam-tilt measurement.

    Images are acquired at equal time intervals at beam tilts
    ``[first_tilt, second_tilt, first_tilt]``.  Because the first and third
    images share a beam tilt, their correlation measures pure specimen drift
    over the whole sequence.  Assuming the drift is linear in time, the second
    image sits at the temporal midpoint, so half of that drift is removed from
    the tilt displacement.  This is the SerialEM three-shot focus scheme and it
    cancels linear drift that a two-shot measurement cannot separate from the
    beam-tilt shift.
    """

    first_tilt: Vector2
    second_tilt: Vector2
    first_image: np.ndarray
    second_image: np.ndarray
    third_image: np.ndarray


@dataclass(frozen=True)
class StageTiltImagePair:
    """Reference and tilted images for one stage-alpha measurement."""

    alpha: float
    reference_image: np.ndarray
    tilted_image: np.ndarray


def solve_objective_focus_from_image_pairs(
    calibration: ObjectiveCalibration,
    image_pairs: Sequence[BeamTiltImagePair],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
    validate: bool = True,
    max_condition_number: float = 1.0e12,
) -> dict:
    """Correlate beam-tilt image pairs and solve objective focus/stig."""

    measurements, shift_results = beam_tilt_measurements_from_images(
        image_pairs,
        camera_binning=camera_binning,
        correlation_type=correlation_type,
        subpixel_window=subpixel_window,
        taper_fraction=taper_fraction,
        pad_fraction=pad_fraction,
        lowpass=lowpass,
        min_snr=min_snr,
    )
    result = solve_defocus_stig(
        calibration.defocus_matrix,
        measurements,
        stigx_matrix=calibration.stigx_matrix,
        stigy_matrix=calibration.stigy_matrix,
        validate=validate,
        max_condition_number=max_condition_number,
    )
    result["measurements"] = measurements
    result["shift_results"] = shift_results
    result["min_snr_observed"] = _min_snr(shift_results)
    return result


def beam_tilt_measurements_from_images(
    image_pairs: Sequence[BeamTiltImagePair],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
) -> tuple[list[BeamTiltMeasurement], list[ShiftResult]]:
    """Build beam-tilt measurements from acquired image pairs."""

    if not image_pairs:
        raise ValueError("at least one beam-tilt image pair is required")

    measurements: list[BeamTiltMeasurement] = []
    shift_results: list[ShiftResult] = []
    for index, pair in enumerate(image_pairs):
        shift = correlate_shift(
            pair.second_image,
            pair.first_image,
            correlation_type=correlation_type,
            subpixel_window=subpixel_window,
            taper_fraction=taper_fraction,
            pad_fraction=pad_fraction,
            lowpass=lowpass,
        )
        _reject_low_snr(shift, index, min_snr)
        shift_results.append(shift)
        measurements.append(
            BeamTiltMeasurement(
                tilt_delta=(
                    pair.second_tilt[0] - pair.first_tilt[0],
                    pair.second_tilt[1] - pair.first_tilt[1],
                ),
                pixel_shift=unbin_pixel_shift(shift.shift, camera_binning),
            )
        )
    return measurements, shift_results


def solve_objective_focus_from_triple_shots(
    calibration: ObjectiveCalibration,
    triple_shots: Sequence[BeamTiltTripleShot],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
    validate: bool = True,
    max_condition_number: float = 1.0e12,
) -> dict:
    """Correlate three-shot beam-tilt triples and solve objective focus/stig.

    Each triple is reduced to a drift-corrected beam-tilt measurement, so this
    is the drift-resistant counterpart of
    :func:`solve_objective_focus_from_image_pairs`.
    """

    measurements, shift_results = beam_tilt_measurements_from_triple_shots(
        triple_shots,
        camera_binning=camera_binning,
        correlation_type=correlation_type,
        subpixel_window=subpixel_window,
        taper_fraction=taper_fraction,
        pad_fraction=pad_fraction,
        lowpass=lowpass,
        min_snr=min_snr,
    )
    result = solve_defocus_stig(
        calibration.defocus_matrix,
        measurements,
        stigx_matrix=calibration.stigx_matrix,
        stigy_matrix=calibration.stigy_matrix,
        validate=validate,
        max_condition_number=max_condition_number,
    )
    result["measurements"] = measurements
    result["shift_results"] = shift_results
    result["min_snr_observed"] = _min_snr(shift_results)
    return result


def beam_tilt_measurements_from_triple_shots(
    triple_shots: Sequence[BeamTiltTripleShot],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
) -> tuple[list[BeamTiltMeasurement], list[ShiftResult]]:
    """Build drift-corrected beam-tilt measurements from three-shot triples.

    For each triple the first/second correlation gives the raw tilt
    displacement (beam-tilt shift plus drift over the first interval) and the
    first/third correlation gives the drift over the whole sequence.  Half of
    that drift is the drift accrued by the temporal-midpoint second image, so
    subtracting it leaves the drift-free beam-tilt displacement.
    """

    if not triple_shots:
        raise ValueError("at least one beam-tilt triple shot is required")

    measurements: list[BeamTiltMeasurement] = []
    shift_results: list[ShiftResult] = []
    for index, triple in enumerate(triple_shots):
        tilt_shift = correlate_shift(
            triple.second_image,
            triple.first_image,
            correlation_type=correlation_type,
            subpixel_window=subpixel_window,
            taper_fraction=taper_fraction,
            pad_fraction=pad_fraction,
            lowpass=lowpass,
        )
        drift_shift = correlate_shift(
            triple.third_image,
            triple.first_image,
            correlation_type=correlation_type,
            subpixel_window=subpixel_window,
            taper_fraction=taper_fraction,
            pad_fraction=pad_fraction,
            lowpass=lowpass,
            zero_origin=False,
        )
        _reject_low_snr(tilt_shift, index, min_snr)
        _reject_low_snr(drift_shift, index, min_snr)
        shift_results.append(tilt_shift)
        shift_results.append(drift_shift)

        corrected = (
            tilt_shift.shift[0] - drift_shift.shift[0] / 2.0,
            tilt_shift.shift[1] - drift_shift.shift[1] / 2.0,
        )
        measurements.append(
            BeamTiltMeasurement(
                tilt_delta=(
                    triple.second_tilt[0] - triple.first_tilt[0],
                    triple.second_tilt[1] - triple.first_tilt[1],
                ),
                pixel_shift=unbin_pixel_shift(corrected, camera_binning),
            )
        )
    return measurements, shift_results


def solve_stage_z_from_image_pairs(
    stage_matrix: np.ndarray,
    image_pairs: Sequence[StageTiltImagePair],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    alpha_for_matrix: float = 0.0,
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
) -> dict:
    """Correlate stage-tilt image pairs and solve Z error."""

    measurements, shift_results = stage_tilt_measurements_from_images(
        image_pairs,
        camera_binning=camera_binning,
        correlation_type=correlation_type,
        subpixel_window=subpixel_window,
        taper_fraction=taper_fraction,
        pad_fraction=pad_fraction,
        lowpass=lowpass,
        min_snr=min_snr,
    )
    result = solve_stage_z(
        stage_matrix,
        measurements,
        camera_binning=(1.0, 1.0),
        alpha_for_matrix=alpha_for_matrix,
    )
    result["measurements"] = measurements
    result["shift_results"] = shift_results
    result["min_snr_observed"] = _min_snr(shift_results)
    return result


def stage_tilt_measurements_from_images(
    image_pairs: Sequence[StageTiltImagePair],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    min_snr: float = 0.0,
) -> tuple[list[StageTiltMeasurement], list[ShiftResult]]:
    """Build stage-tilt Z measurements from reference/tilted images."""

    if not image_pairs:
        raise ValueError("at least one stage-tilt image pair is required")

    measurements: list[StageTiltMeasurement] = []
    shift_results: list[ShiftResult] = []
    for index, pair in enumerate(image_pairs):
        shift = correlate_shift(
            pair.tilted_image,
            pair.reference_image,
            correlation_type=correlation_type,
            subpixel_window=subpixel_window,
            taper_fraction=taper_fraction,
            pad_fraction=pad_fraction,
            lowpass=lowpass,
        )
        _reject_low_snr(shift, index, min_snr)
        shift_results.append(shift)
        measurements.append(
            StageTiltMeasurement(
                alpha=pair.alpha,
                pixel_shift=unbin_pixel_shift(shift.shift, camera_binning),
            )
        )
    return measurements, shift_results


def unbin_pixel_shift(pixel_shift: Vector2, camera_binning: Vector2) -> Vector2:
    """Convert a binned ``(row, col)`` shift to unbinned pixels."""

    bin_y, bin_x = camera_binning
    if not np.all(np.isfinite((pixel_shift[0], pixel_shift[1], bin_y, bin_x))):
        raise ValueError("pixel_shift and camera_binning must be finite")
    if bin_y <= 0.0 or bin_x <= 0.0:
        raise ValueError("camera_binning values must be positive")
    return (float(pixel_shift[0] * bin_y), float(pixel_shift[1] * bin_x))


def _reject_low_snr(shift: ShiftResult, index: int, min_snr: float) -> None:
    """Raise when a correlation peak is too weak to trust.

    ``min_snr <= 0`` disables the check, so callers that have not chosen a
    threshold keep the previous unguarded behavior.
    """

    if min_snr <= 0.0:
        return
    if shift.snr < min_snr:
        raise ValueError(
            f"correlation SNR {shift.snr:.3g} for image pair {index} "
            f"is below the required minimum {min_snr:.3g}"
        )


def _min_snr(shift_results: Sequence[ShiftResult]) -> float:
    """Return the weakest correlation SNR across a set of measurements."""

    return min((result.snr for result in shift_results), default=float("nan"))


"""Objective-lens autofocus from beam-tilt image displacements.

Leginon performs beam-tilt autofocus by acquiring image pairs at two beam
tilts, correlating each pair, and solving a calibrated linear system for
defocus and optionally objective stigmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

import numpy as np


Vector2 = Tuple[float, float]


@dataclass(frozen=True)
class BeamTiltMeasurement:
    """One beam-tilt displacement measurement.

    ``tilt_delta`` is ``(delta_x, delta_y)`` in beam-tilt units between the
    second and first image.  ``pixel_shift`` is the correlated image shift
    ``(row, col)`` in unbinned pixels.
    """

    tilt_delta: Vector2
    pixel_shift: Vector2


@dataclass(frozen=True)
class FocusSolveDiagnostics:
    """Numerical diagnostics for a defocus/stigmation solve."""

    design: np.ndarray
    observed: np.ndarray
    predicted: np.ndarray
    residual_vector: np.ndarray
    residual: float
    rank: int
    unknown_count: int
    singular_values: np.ndarray
    condition_number: float


@dataclass(frozen=True)
class ObjectiveFocusResult:
    """Result of a calibrated objective-focus solve."""

    defocus: float
    stigx: Optional[float]
    stigy: Optional[float]
    residual: float
    residual_vector: np.ndarray
    rank: int
    unknown_count: int
    singular_values: np.ndarray
    condition_number: float
    diagnostics: FocusSolveDiagnostics
    measurements: Tuple[Any, ...] = ()
    shift_results: Tuple[Any, ...] = ()
    min_snr_observed: float = float("nan")
    min_peak_ratio_observed: float = float("nan")
    min_normalized_ccc_observed: float = float("nan")


def solve_defocus_stig(
    defocus_matrix: np.ndarray,
    measurements: Sequence[BeamTiltMeasurement],
    *,
    stigx_matrix: Optional[np.ndarray] = None,
    stigy_matrix: Optional[np.ndarray] = None,
    validate: bool = True,
    max_condition_number: float = 1.0e12,
) -> ObjectiveFocusResult:
    """Solve defocus and optional objective stigmation.

    This is a standalone version of Leginon's calibrated ``solveEq10`` matrix
    solve.  With one measurement and only ``defocus_matrix`` it returns
    defocus.  With two sufficiently independent measurements and both stig
    matrices it returns defocus, stigx, and stigy.

    By default the solver rejects rank-deficient and badly conditioned designs.
    This is stricter than Leginon, but it prevents invalid tilt geometry from
    producing plausible-looking corrections.
    """

    matrices = [_matrix2(defocus_matrix, "defocus_matrix")]
    if (stigx_matrix is None) != (stigy_matrix is None):
        raise ValueError("stigx_matrix and stigy_matrix must be provided together")
    if stigx_matrix is not None and stigy_matrix is not None:
        matrices.extend([
            _matrix2(stigx_matrix, "stigx_matrix"),
            _matrix2(stigy_matrix, "stigy_matrix"),
        ])

    if not measurements:
        raise ValueError("at least one beam-tilt measurement is required")

    observed, design = _build_defocus_design(matrices, measurements)

    solution, residuals, rank, singular_values = np.linalg.lstsq(design, observed, rcond=None)
    predicted = design @ solution
    residual_vector = observed - predicted
    residual = float(residual_vector @ residual_vector)
    condition_number = _condition_number(singular_values)
    unknown_count = len(matrices)

    if validate:
        _validate_solve_geometry(
            rank=int(rank),
            unknown_count=unknown_count,
            condition_number=condition_number,
            max_condition_number=max_condition_number,
        )

    diagnostics = FocusSolveDiagnostics(
        design=design,
        observed=observed,
        predicted=predicted,
        residual_vector=residual_vector,
        residual=residual,
        rank=int(rank),
        unknown_count=unknown_count,
        singular_values=singular_values,
        condition_number=condition_number,
    )
    return ObjectiveFocusResult(
        defocus=float(solution[0]),
        stigx=float(solution[1]) if len(solution) == 3 else None,
        stigy=float(solution[2]) if len(solution) == 3 else None,
        residual=float(residuals[0]) if len(residuals) else residual,
        residual_vector=residual_vector,
        rank=int(rank),
        unknown_count=unknown_count,
        singular_values=singular_values,
        condition_number=condition_number,
        diagnostics=diagnostics,
    )


def solve_rotation_center_tilt(
    defocus_matrix: np.ndarray,
    defocus1: float,
    defocus2: float,
    pixel_shift: Vector2,
    *,
    max_condition_number: float = 1.0e12,
) -> Vector2:
    """Solve beam-tilt misalignment from a defocus-change displacement.

    The two defoci must differ and the calibration matrix must be invertible;
    otherwise the misalignment is unobservable and a clear error is raised
    rather than letting ``numpy`` fail on a singular system.
    """

    matrix = _matrix2(defocus_matrix, "defocus_matrix")
    defocus_change = float(defocus2) - float(defocus1)
    if abs(defocus_change) < 1.0e-12:
        raise ValueError("defocus1 and defocus2 must differ to solve beam-tilt misalignment")

    shift = np.asarray(pixel_shift, dtype=np.float64)
    if shift.shape != (2,):
        raise ValueError("pixel_shift must contain exactly two values")
    if not np.all(np.isfinite(shift)):
        raise ValueError("pixel_shift must contain finite values")

    delta = defocus_change * matrix
    condition_number = _condition_number(np.linalg.svd(delta, compute_uv=False))
    if not np.isfinite(condition_number) or condition_number > max_condition_number:
        raise ValueError(
            "defocus calibration matrix is singular or poorly conditioned: "
            f"condition number {condition_number:.3g}"
        )

    tilt = np.linalg.solve(delta, shift)
    return (float(tilt[0]), float(tilt[1]))


def default_beam_tilt_pair(scale: float) -> Tuple[Vector2, Vector2]:
    """Return Leginon's default pair of beam-tilt offsets for a scale."""

    return ((0.0, 0.0), (float(scale), 0.0))


def rotate_vector(vector: Vector2, radians: float) -> Vector2:
    """Rotate an ``(x, y)`` vector about the origin."""

    x, y = vector
    cos_r = np.cos(radians)
    sin_r = np.sin(radians)
    return (float(x * cos_r - y * sin_r), float(x * sin_r + y * cos_r))


def measurements_from_pairs(
    tilt_pairs: Iterable[Tuple[Vector2, Vector2]],
    pixel_shifts: Iterable[Vector2],
) -> list[BeamTiltMeasurement]:
    """Build measurements from first/second beam tilts and image shifts."""

    measurements = []
    for (tilt1, tilt2), shift in zip(tilt_pairs, pixel_shifts):
        measurements.append(
            BeamTiltMeasurement(
                tilt_delta=(tilt2[0] - tilt1[0], tilt2[1] - tilt1[1]),
                pixel_shift=shift,
            )
        )
    return measurements


def _build_defocus_design(
    matrices: Sequence[np.ndarray],
    measurements: Sequence[BeamTiltMeasurement],
) -> Tuple[np.ndarray, np.ndarray]:
    observed = np.asarray([m.pixel_shift for m in measurements], dtype=np.float64).ravel()
    blocks = []
    for measurement in measurements:
        tilt = np.asarray(measurement.tilt_delta, dtype=np.float64).reshape(2, 1)
        if tilt.shape != (2, 1):
            raise ValueError("tilt_delta must contain exactly two values")
        blocks.append(np.concatenate([matrix @ tilt for matrix in matrices], axis=1))
    design = np.concatenate(blocks, axis=0)
    if observed.shape[0] != design.shape[0]:
        raise ValueError("pixel_shift values must contain exactly two values per measurement")
    if not np.all(np.isfinite(observed)) or not np.all(np.isfinite(design)):
        raise ValueError("tilts, shifts, and calibration matrices must be finite")
    return observed, design


def _condition_number(singular_values: np.ndarray) -> float:
    if singular_values.size == 0:
        return float("inf")
    smallest = float(np.min(singular_values))
    largest = float(np.max(singular_values))
    if smallest <= 0.0:
        return float("inf")
    return largest / smallest


def _validate_solve_geometry(
    *,
    rank: int,
    unknown_count: int,
    condition_number: float,
    max_condition_number: float,
) -> None:
    if rank < unknown_count:
        raise ValueError(
            f"focus solve is rank deficient: rank {rank} for {unknown_count} unknowns"
        )
    if not np.isfinite(condition_number):
        raise ValueError("focus solve is singular")
    if condition_number > max_condition_number:
        raise ValueError(
            "focus solve is poorly conditioned: "
            f"condition number {condition_number:.3g} exceeds {max_condition_number:.3g}"
        )


def _matrix2(matrix: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(matrix, dtype=np.float64)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must be a 2x2 matrix")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite values")
    return array

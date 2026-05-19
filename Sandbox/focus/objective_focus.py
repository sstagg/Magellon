"""Objective-lens autofocus from beam-tilt image displacements.

Leginon performs beam-tilt autofocus by acquiring image pairs at two beam
tilts, correlating each pair, and solving Koster equation 10 with calibration
matrices for defocus and optionally objective stigmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

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


def solve_defocus_stig(
    defocus_matrix: np.ndarray,
    measurements: Sequence[BeamTiltMeasurement],
    *,
    stigx_matrix: Optional[np.ndarray] = None,
    stigy_matrix: Optional[np.ndarray] = None,
) -> dict:
    """Solve defocus and optional objective stigmation.

    This is a standalone version of Leginon's ``solveEq10``.  With one
    measurement and only ``defocus_matrix`` it returns defocus.  With two
    sufficiently independent measurements and both stig matrices it returns
    defocus, stigx, and stigy.
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

    observed = np.asarray([m.pixel_shift for m in measurements], dtype=np.float64).ravel()
    blocks = []
    for measurement in measurements:
        tilt = np.asarray(measurement.tilt_delta, dtype=np.float64).reshape(2, 1)
        blocks.append(np.concatenate([matrix @ tilt for matrix in matrices], axis=1))
    design = np.concatenate(blocks, axis=0)

    solution, residuals, rank, singular_values = np.linalg.lstsq(design, observed, rcond=None)
    result = {
        "defocus": float(solution[0]),
        "stigx": float(solution[1]) if len(solution) == 3 else None,
        "stigy": float(solution[2]) if len(solution) == 3 else None,
        "residual": float(residuals[0]) if len(residuals) else 0.0,
        "rank": int(rank),
        "singular_values": singular_values,
    }
    return result


def solve_rotation_center_tilt(
    defocus_matrix: np.ndarray,
    defocus1: float,
    defocus2: float,
    pixel_shift: Vector2,
) -> Vector2:
    """Solve beam-tilt misalignment from a defocus-change displacement."""

    matrix = _matrix2(defocus_matrix, "defocus_matrix")
    delta = (defocus2 - defocus1) * matrix
    tilt = np.linalg.solve(delta, np.asarray(pixel_shift, dtype=np.float64))
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


def _matrix2(matrix: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(matrix, dtype=np.float64)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must be a 2x2 matrix")
    return array

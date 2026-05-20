"""Stage-tilt Z autofocus from correlated image displacements.

Leginon's Z focus tilts the stage in both alpha directions, correlates each
tilted image against the untilted image, converts the image displacement to
stage X/Y motion with a calibration matrix, and estimates Z from the Y motion
divided by ``sin(alpha)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np


Vector2 = Tuple[float, float]


@dataclass(frozen=True)
class StageTiltMeasurement:
    """One stage-tilt displacement measurement.

    ``alpha`` is the stage tilt angle in radians.  ``pixel_shift`` is the
    correlated image shift ``(row, col)`` in unbinned pixels.
    """

    alpha: float
    pixel_shift: Vector2


def solve_stage_z(
    stage_matrix: np.ndarray,
    measurements: Sequence[StageTiltMeasurement],
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    alpha_for_matrix: float = 0.0,
) -> dict:
    """Estimate Z error from stage-tilt image shifts.

    ``stage_matrix`` maps pixel vector ``(row, col)`` to stage movement
    ``(x, y)``.  It is the same kind of matrix Leginon's stage calibration
    client retrieves from the database.
    """

    matrix = np.asarray(stage_matrix, dtype=np.float64)
    if matrix.shape != (2, 2):
        raise ValueError("stage_matrix must be a 2x2 matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("stage_matrix must contain finite values")
    if not measurements:
        raise ValueError("at least one stage-tilt measurement is required")

    z_values = []
    xy_values = []
    for measurement in measurements:
        if abs(np.sin(measurement.alpha)) < 1e-12:
            raise ValueError("stage tilt alpha is too close to zero")
        stage_xy = pixel_shift_to_stage_xy(
            matrix,
            measurement.pixel_shift,
            camera_binning=camera_binning,
            alpha=alpha_for_matrix,
        )
        xy_values.append(stage_xy)
        z_values.append(stage_xy[1] / np.sin(measurement.alpha))

    z_array = np.asarray(z_values, dtype=np.float64)
    z_mean = float(np.mean(z_array))
    return {
        "z": z_mean,
        "z_values": z_array,
        "stage_xy": xy_values,
        "z_std": float(np.std(z_array)),
        "z_range": float(np.max(z_array) - np.min(z_array)),
        "measurement_count": len(measurements),
    }


def pixel_shift_to_stage_xy(
    stage_matrix: np.ndarray,
    pixel_shift: Vector2,
    *,
    camera_binning: Vector2 = (1.0, 1.0),
    alpha: float = 0.0,
) -> Vector2:
    """Convert a pixel shift ``(row, col)`` to stage ``(x, y)`` movement."""

    bin_y, bin_x = camera_binning
    if not np.all(np.isfinite((bin_y, bin_x, alpha))):
        raise ValueError("camera_binning and alpha must be finite")
    if abs(np.cos(alpha)) < 1e-12:
        raise ValueError("alpha for matrix conversion is too close to 90 degrees")
    pixel_vector = np.asarray(
        (pixel_shift[0] * bin_y, pixel_shift[1] * bin_x),
        dtype=np.float64,
    )
    matrix = np.asarray(stage_matrix, dtype=np.float64)
    if matrix.shape != (2, 2):
        raise ValueError("stage_matrix must be a 2x2 matrix")
    if not np.all(np.isfinite(pixel_vector)) or not np.all(np.isfinite(matrix)):
        raise ValueError("stage_matrix and pixel_shift must contain finite values")
    change = matrix @ pixel_vector
    x = float(change[0])
    y = float(change[1] / np.cos(alpha))
    return (x, y)

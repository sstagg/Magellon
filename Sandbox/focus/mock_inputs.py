"""Synthetic inputs for exercising the extracted focus algorithms."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from .correlation import correlate_shift
from .objective_focus import BeamTiltMeasurement, solve_defocus_stig
from .z_focus import StageTiltMeasurement, solve_stage_z


def shifted_image_demo(shift: Tuple[int, int] = (7, -4), shape: Tuple[int, int] = (96, 96)) -> dict:
    """Create a simple synthetic image pair and recover its shift."""

    rng = np.random.default_rng(7)
    image = rng.normal(0.0, 0.03, shape)
    rr, cc = np.indices(shape)
    image += np.exp(-(((rr - 32.5) ** 2 + (cc - 41.0) ** 2) / (2.0 * 3.0**2)))
    image += 0.7 * np.exp(-(((rr - 68.0) ** 2 + (cc - 59.5) ** 2) / (2.0 * 5.0**2)))
    shifted = np.roll(np.roll(image, shift[0], axis=0), shift[1], axis=1)
    result = correlate_shift(shifted, image, correlation_type="phase")
    return {"expected_shift": shift, "measured_shift": result.shift, "snr": result.snr}


def objective_focus_demo() -> dict:
    """Solve a noiseless beam-tilt defocus/stig example."""

    defocus_matrix = np.array([[1200.0, 30.0], [-20.0, 1000.0]])
    stigx_matrix = np.array([[200.0, -50.0], [40.0, 150.0]])
    stigy_matrix = np.array([[-80.0, 180.0], [160.0, 20.0]])
    truth = np.array([2.0e-6, -0.4e-6, 0.7e-6])
    tilts = [(0.01, 0.0), (0.0, 0.01)]
    measurements = []
    for tilt in tilts:
        design = np.concatenate([
            defocus_matrix @ np.asarray(tilt).reshape(2, 1),
            stigx_matrix @ np.asarray(tilt).reshape(2, 1),
            stigy_matrix @ np.asarray(tilt).reshape(2, 1),
        ], axis=1)
        shift = design @ truth
        measurements.append(BeamTiltMeasurement(tilt, (float(shift[0]), float(shift[1]))))
    return solve_defocus_stig(
        defocus_matrix,
        measurements,
        stigx_matrix=stigx_matrix,
        stigy_matrix=stigy_matrix,
    )


def z_focus_demo() -> dict:
    """Solve a noiseless stage-tilt Z example."""

    stage_matrix = np.array([[1.0e-9, 0.0], [0.0, 2.0e-9]])
    z_truth = 1.5e-6
    alpha = 0.1
    y_shift = z_truth * np.sin(alpha)
    # stage_matrix maps col pixels to y stage movement in this toy example.
    col_pixels = y_shift / stage_matrix[1, 1]
    measurements = [
        StageTiltMeasurement(-alpha, (0.0, -col_pixels)),
        StageTiltMeasurement(alpha, (0.0, col_pixels)),
    ]
    return solve_stage_z(stage_matrix, measurements)

from __future__ import annotations

import numpy as np

import utils

threshold_image = utils.threshold_image


MEAN_STD_METHOD = "Threshold = mean + A * stdev"
FIXED_METHOD = "Threshold = A"


def threshold_correlation(
    correlation: np.ndarray,
    threshold_value: float,
    threshold_method: str = MEAN_STD_METHOD,
) -> np.ndarray:
    if threshold_method == MEAN_STD_METHOD:
        threshold = float(correlation.mean()) + float(threshold_value) * float(correlation.std())
    elif threshold_method == FIXED_METHOD:
        threshold = float(threshold_value)
    else:
        raise ValueError(f"Unsupported threshold_method: {threshold_method}")
    return threshold_image(correlation, threshold)

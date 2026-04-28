from __future__ import annotations

import numpy as np
import scipy.ndimage


def apply_gaussian_filter(image: np.ndarray, sigma: float | None) -> np.ndarray:
    if sigma is None:
        return image
    return scipy.ndimage.gaussian_filter(image, sigma)


def threshold_image(image: np.ndarray, threshold: float) -> np.ndarray:
    return (image >= threshold).astype(np.uint8)

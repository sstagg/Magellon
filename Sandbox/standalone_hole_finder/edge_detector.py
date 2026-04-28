from __future__ import annotations

import numpy as np
import scipy.ndimage

import utils

threshold_image = utils.threshold_image


def find_edges(image: np.ndarray, lpsig: float = 1.0, thresh: float | None = 100.0) -> np.ndarray:
    smooth = scipy.ndimage.gaussian_filter(image, lpsig)
    edges = scipy.ndimage.generic_gradient_magnitude(smooth, derivative=scipy.ndimage.sobel)
    if thresh is not None:
        edges = threshold_image(edges, float(thresh)).astype(np.float32)
    return edges.astype(np.float32)

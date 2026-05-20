"""Image preprocessing for MicAssess micrographs and 2D class averages.

Historical note: the original ``lib/utils.py`` exposed three micrograph
preprocessing functions (``preprocess_c``/``_l``/``_r``) that passed different
circular-mask centres for the K2 and K3 left/right paths.  The underlying
``mask_img`` discarded the ``center`` argument it was given, so all three were
numerically identical -- a centred circular mask.  The shipped models were
therefore trained and run with a centred mask regardless of detector, so this
module exposes a single :func:`preprocess_micrograph`.  K3 left/right handling
lives entirely in the model graph's crop layer, not in preprocessing.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

_EPS = 1e-8


def normalize(image: np.ndarray) -> np.ndarray:
    """Return a zero-mean, unit-variance copy of ``image`` as ``float64``."""

    array = np.asarray(image, dtype=np.float64)
    std = float(np.std(array))
    return (array - float(np.mean(array))) / (std + _EPS)


def circular_mask(
    height: int,
    width: int,
    center: Optional[Tuple[float, float]] = None,
    radius: Optional[float] = None,
) -> np.ndarray:
    """Return a boolean circular mask.

    ``center`` is ``(x, y)`` in pixel coordinates and defaults to the image
    centre; ``radius`` defaults to the largest circle that fits inside the
    frame around ``center``.
    """

    if center is None:
        center = (width // 2, height // 2)
    if radius is None:
        radius = min(center[0], center[1], width - center[0], height - center[1])
    yy, xx = np.ogrid[:height, :width]
    return (xx - center[0]) ** 2 + (yy - center[1]) ** 2 <= radius ** 2


def apply_circular_mask(
    image: np.ndarray,
    center: Optional[Tuple[float, float]] = None,
    radius: Optional[float] = None,
) -> np.ndarray:
    """Zero everything outside a circular mask.

    Unlike the original ``lib/utils.mask_img``, this honours ``center`` and
    ``radius`` -- the old function silently ignored them.
    """

    array = np.asarray(image)
    mask = circular_mask(array.shape[0], array.shape[1], center, radius)
    masked = array.copy()
    masked[~mask] = 0
    return masked


def preprocess_micrograph(image: np.ndarray) -> np.ndarray:
    """Normalise then apply a centred circular mask -- the MicAssess transform.

    This is the single preprocessing function fed to the model's image
    generator for every detector; see the module docstring for why the K2/K3
    variants collapsed to one.
    """

    return apply_circular_mask(normalize(image))


def preprocess_class_average(image: np.ndarray) -> np.ndarray:
    """Normalise then apply a centred circular mask -- the 2DAssess transform."""

    return apply_circular_mask(normalize(image))


def cut_by_radius(image: np.ndarray) -> np.ndarray:
    """Crop a masked 2D class average down to its non-empty region.

    Class averages from RELION arrive with a zeroed circular border; this finds
    the smallest border inset that still touches content and crops symmetrically.
    Ported from the original ``lib/imgprep.cutByRadius`` with its heuristic
    intact.
    """

    height, width = image.shape[0], image.shape[1]

    def first_content_edge(reverse: bool) -> int:
        span = range(width)
        for offset in span:
            index = -offset if reverse else offset
            row_sum = np.sum(image[index, :])
            col_sum = np.sum(image[:, index])
            if row_sum > _EPS or col_sum < -_EPS:
                return offset
        return 0

    edge = min(first_content_edge(False), first_content_edge(True))
    return image[edge:height - edge + 1, edge:width - edge + 1]

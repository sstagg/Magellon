"""Saliency-based centering check for 2D class averages.

Used by 2DAssess to demote an otherwise-"good" class average to the "clipping"
bucket when its content is off-centre or split into multiple objects.

``opencv-python`` and ``scikit-image`` are imported lazily so the rest of
``cryoassess.core`` stays importable without them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image

PathLike = Union[str, Path]

_SALIENCY_THRESHOLD = 0.2
_OFF_CENTER_TOLERANCE = 0.15
_MIN_OBJECT_AREA = 40
_RELATIVE_OBJECT_AREA = 0.5


def is_centered(image_path: PathLike) -> bool:
    """Return True if the class average is single-object and roughly centred."""

    import cv2
    from scipy import ndimage
    from skimage import measure

    image = np.asarray(Image.open(str(image_path)))

    saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
    _, saliency_map = saliency.computeSaliency(image)

    binary = np.where(saliency_map > _SALIENCY_THRESHOLD, 1, 0)
    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(np.float32(binary), cv2.MORPH_CLOSE, kernel)

    regions = measure.regionprops(measure.label(binary, background=0))
    if not regions:
        return False

    max_area = max(region.area for region in regions)
    object_count = sum(
        1
        for region in regions
        if region.area > max(_RELATIVE_OBJECT_AREA * max_area, _MIN_OBJECT_AREA)
    )

    centerness = np.divide(ndimage.center_of_mass(binary), binary.shape)
    off_center = (
        abs(centerness[0] - 0.5) > _OFF_CENTER_TOLERANCE
        or abs(centerness[1] - 0.5) > _OFF_CENTER_TOLERANCE
    )
    return not (off_center or object_count > 1)

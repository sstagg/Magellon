import glob
import os

import numpy as np
import pytest
from PIL import Image

from cryoassess.core.preprocessing import (
    apply_circular_mask,
    circular_mask,
    cut_by_radius,
    normalize,
    preprocess_micrograph,
)


def test_normalize_zero_mean_unit_std():
    rng = np.random.default_rng(0)
    out = normalize(rng.normal(5.0, 3.0, (20, 30)))
    assert abs(float(out.mean())) < 1e-9
    assert abs(float(out.std()) - 1.0) < 1e-6


def test_normalize_constant_image_is_finite():
    # a flat image has zero std; the epsilon must keep the result finite
    out = normalize(np.full((10, 10), 7.0))
    assert np.all(np.isfinite(out))


def test_circular_mask_shape_center_and_corners():
    mask = circular_mask(50, 60)
    assert mask.shape == (50, 60)
    assert mask[25, 30]       # centre is inside
    assert not mask[0, 0]     # corner is outside


def test_apply_circular_mask_zeros_corners_keeps_centre():
    image = np.ones((40, 40))
    masked = apply_circular_mask(image)
    assert masked[0, 0] == 0
    assert masked[20, 20] == 1


def test_apply_circular_mask_honours_custom_center():
    # regression: the original mask_img silently ignored center/radius
    image = np.ones((40, 40))
    centred = apply_circular_mask(image)
    shifted = apply_circular_mask(image, center=(10, 20), radius=8)
    assert not np.array_equal(centred, shifted)
    assert shifted[20, 10] == 1   # (row 20, col 10) is inside the shifted disk
    assert shifted[39, 39] == 0   # far corner is outside it


def test_preprocess_micrograph_masks_and_keeps_shape():
    rng = np.random.default_rng(1)
    out = preprocess_micrograph(rng.normal(0.0, 1.0, (64, 64)))
    assert out.shape == (64, 64)
    assert out[0, 0] == 0         # corner masked away


def test_cut_by_radius_crops_empty_border():
    image = np.zeros((20, 20))
    image[8:12, 8:12] = 1.0
    cropped = cut_by_radius(image)
    assert cropped.shape[0] < 20 and cropped.shape[1] < 20
    assert float(cropped.sum()) == 16.0   # all the content is retained


def test_preprocess_real_example_png():
    pattern = os.path.join(os.path.dirname(__file__), "..", "Examples", "*", "*.png")
    examples = sorted(glob.glob(pattern))
    if not examples:
        pytest.skip("no example PNGs available")
    image = np.asarray(Image.open(examples[0]).convert("L"), dtype=float)
    out = preprocess_micrograph(image)
    assert out.shape == image.shape
    assert np.all(np.isfinite(out))

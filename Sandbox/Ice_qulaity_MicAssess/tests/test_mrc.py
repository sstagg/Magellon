import mrcfile
import numpy as np

from cryoassess.core.mrc import (
    crop_center,
    crop_left,
    crop_right,
    fft_downsample,
    load_micrograph,
    load_stack,
    scale_to_uint8,
    to_grayscale_image,
)


def test_fft_downsample_hits_target_height():
    image = np.random.default_rng(0).normal(0.0, 1.0, (988, 1024))
    out = fft_downsample(image, height=494)
    assert out.shape[0] == 494


def test_fft_downsample_width_is_even():
    image = np.random.default_rng(0).normal(0.0, 1.0, (988, 1100))
    assert fft_downsample(image, 494).shape[1] % 2 == 0


def test_scale_to_uint8_spans_full_range():
    scaled = scale_to_uint8(np.array([[-5.0, 0.0], [3.0, 10.0]]))
    assert scaled.dtype == np.uint8
    # the brightest pixel reaches 254 not 255: the +1e-7 denominator epsilon
    # plus uint8 truncation, preserved from the original scaleImage.
    assert scaled.min() == 0
    assert 254 <= scaled.max() <= 255


def test_to_grayscale_image_is_8bit_at_target_height():
    image = np.random.default_rng(0).normal(0.0, 1.0, (988, 1024))
    pil_image = to_grayscale_image(image, height=494)
    assert pil_image.mode == "L"
    assert pil_image.size[1] == 494   # PIL size is (width, height)


def test_crop_center_left_right():
    image = np.arange(100).reshape(10, 10)
    assert crop_center(image, 4, 4).shape == (4, 4)

    left = crop_left(image, 4, 6)
    assert left.shape == (6, 4)
    assert np.array_equal(left[:, 0], image[2:8, 0])

    right = crop_right(image, 4, 6)
    assert right.shape == (6, 4)
    assert np.array_equal(right[:, -1], image[2:8, 9])


def test_load_micrograph_roundtrip(tmp_path):
    data = np.random.default_rng(0).normal(0.0, 1.0, (64, 80)).astype(np.float32)
    path = tmp_path / "m.mrc"
    with mrcfile.new(str(path)) as mrc:
        mrc.set_data(data)
    loaded = load_micrograph(path)
    assert loaded.shape == (64, 80)
    assert np.allclose(loaded, data, atol=1e-5)


def test_load_stack_keeps_three_dims(tmp_path):
    data = np.random.default_rng(0).normal(0.0, 1.0, (5, 32, 32)).astype(np.float32)
    path = tmp_path / "s.mrcs"
    with mrcfile.new(str(path)) as mrc:
        mrc.set_data(data)
    assert load_stack(path).shape == (5, 32, 32)


def test_load_stack_promotes_single_image(tmp_path):
    data = np.random.default_rng(0).normal(0.0, 1.0, (32, 32)).astype(np.float32)
    path = tmp_path / "one.mrc"
    with mrcfile.new(str(path)) as mrc:
        mrc.set_data(data)
    assert load_stack(path).shape == (1, 32, 32)

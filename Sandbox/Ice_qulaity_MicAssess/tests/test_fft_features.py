import numpy as np

from cryoassess.core.fft_features import (
    power_spectrum,
    radial_average,
    radial_log_power_spectrum,
    radial_log_power_spectrum_sigmoid,
)


def test_power_spectrum_is_non_negative():
    image = np.random.default_rng(0).normal(0.0, 1.0, (32, 32))
    assert np.all(power_spectrum(image) >= 0)


def test_radial_average_length_is_half_min_dimension():
    image = np.random.default_rng(0).normal(0.0, 1.0, (64, 80))
    assert len(radial_average(image)) == 32  # min(64, 80) // 2


def test_radial_average_of_constant_image_is_constant():
    image = np.full((48, 48), 4.0)
    profile = radial_average(image)
    assert np.allclose(profile, 4.0)


def test_radial_log_power_spectrum_is_finite():
    image = np.random.default_rng(0).normal(0.0, 1.0, (48, 48)) + 10.0
    assert np.all(np.isfinite(radial_log_power_spectrum(image)))


def test_sigmoid_feature_is_within_unit_interval():
    image = np.random.default_rng(0).normal(0.0, 1.0, (48, 48)) + 10.0
    feature = radial_log_power_spectrum_sigmoid(image)
    assert np.all((feature > 0.0) & (feature < 1.0))

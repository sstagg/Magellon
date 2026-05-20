"""Radial-average log-power-spectrum features (numpy reference implementation).

MicAssess augments its CNN features with the radially averaged log power
spectrum of each micrograph, which captures ice-ring and CTF structure.  This
module is the dependency-free numpy reference and is what the test-suite
checks.  The TensorFlow graph equivalent used inside the live model lives in
:mod:`cryoassess.models.fft_layer`.
"""

from __future__ import annotations

import numpy as np


def power_spectrum(image: np.ndarray) -> np.ndarray:
    """Return the centred 2-D power spectrum of a real image."""

    array = np.asarray(image, dtype=np.float64)
    spectrum = np.fft.fftshift(np.fft.fft2(np.fft.fftshift(array)))
    return np.abs(spectrum) ** 2


def radial_average(image: np.ndarray) -> np.ndarray:
    """Return the mean value of ``image`` in unit-width rings about its centre.

    The result has ``min(height, width) // 2`` entries, one per radius.
    """

    array = np.asarray(image, dtype=np.float64)
    y0 = array.shape[0] // 2
    x0 = array.shape[1] // 2
    xx, yy = np.meshgrid(np.arange(array.shape[1]), np.arange(array.shape[0]))
    distance = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)

    max_radius = min(array.shape[0], array.shape[1]) // 2
    radii = np.linspace(1, max_radius, num=max_radius)
    means = np.array(
        [array[(distance >= r - 0.5) & (distance < r + 0.5)].mean() for r in radii]
    )
    return means


def radial_log_power_spectrum(image: np.ndarray) -> np.ndarray:
    """Return the radial average of the log power spectrum of ``image``."""

    return radial_average(np.log(power_spectrum(image)))


def radial_log_power_spectrum_sigmoid(image: np.ndarray) -> np.ndarray:
    """Sigmoid-squashed :func:`radial_log_power_spectrum`, the model feature."""

    feature = radial_log_power_spectrum(image)
    return 1.0 / (1.0 + np.exp(-feature))

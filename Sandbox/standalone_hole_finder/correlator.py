from __future__ import annotations

import numpy as np
import scipy.signal

import utils

apply_gaussian_filter = utils.apply_gaussian_filter


def mask_black(image: np.ndarray, cor_image_min: float | None) -> np.ndarray:
    if cor_image_min is None:
        return image
    masked = np.ma.masked_less(image, cor_image_min)
    return masked.filled(float(masked.mean()))


def _phase_correlation(source_image: np.ndarray, template: np.ndarray) -> np.ndarray:
    source_fft = np.fft.fft2(source_image)
    template_fft = np.fft.fft2(template)
    cross_power = source_fft * np.conj(template_fft)
    magnitude = np.abs(cross_power)
    magnitude[magnitude == 0] = 1.0
    response = np.fft.ifft2(cross_power / magnitude)
    return np.abs(response).astype(np.float32)


def correlate_template(
    source_image: np.ndarray,
    template: np.ndarray,
    correlation_type: str = "cross",
    correlation_filter_sigma: float | None = 1.0,
    cor_image_min: float | None = 0.0,
) -> np.ndarray:
    source_image = mask_black(source_image, cor_image_min)
    if correlation_type == "cross":
        correlation = scipy.signal.fftconvolve(source_image, template[::-1, ::-1], mode="same")
    elif correlation_type == "phase":
        correlation = _phase_correlation(source_image, template)
    else:
        raise ValueError(f"Unsupported correlation_type: {correlation_type}")
    correlation = apply_gaussian_filter(correlation.astype(np.float32), correlation_filter_sigma)
    return correlation.astype(np.float32)

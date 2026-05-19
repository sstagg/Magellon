"""Image correlation helpers used by the focus algorithms.

The implementation follows the numerical behavior of Leginon's
``pyami.correlator`` and ``pyami.peakfinder`` in a standalone form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

import numpy as np


CorrelationType = Literal["phase", "cross"]


@dataclass(frozen=True)
class ShiftResult:
    """Measured image displacement in pixels.

    ``shift`` is returned as ``(row, col)`` and follows Leginon's wrapped
    correlation convention: positive values mean the correlation peak was
    before the FFT wrap boundary, negative values mean it wrapped past it.
    """

    shift: Tuple[float, float]
    peak: Tuple[float, float]
    peak_value: float
    correlation: np.ndarray
    snr: float


def cross_correlate(image1: np.ndarray, image2: np.ndarray) -> np.ndarray:
    """Return the FFT cross-correlation image for two same-shaped images."""

    im1, im2 = _validated_pair(image1, image2)
    ccfft = np.conjugate(np.fft.fft2(im2)) * np.fft.fft2(im1)
    return np.fft.ifft2(ccfft).real


def phase_correlate(
    image1: np.ndarray,
    image2: np.ndarray,
    *,
    zero_origin: bool = True,
    wiener: bool = False,
) -> np.ndarray:
    """Return phase correlation for two same-shaped images."""

    im1, im2 = _validated_pair(image1, image2)
    ccfft = np.conjugate(np.fft.fft2(im2)) * np.fft.fft2(im1)
    if wiener:
        rstart = int(0.4 * ccfft.shape[0])
        rstop = int(0.5 * ccfft.shape[0])
        region = ccfft[rstart:rstop]
        noise = 10.0 * np.mean(region.real * region.real + region.imag * region.imag)
        denom = np.sqrt(ccfft.real * ccfft.real + ccfft.imag * ccfft.imag + noise)
    else:
        denom = np.abs(ccfft)

    with np.errstate(divide="ignore", invalid="ignore"):
        pcfft = np.divide(ccfft, denom, out=np.zeros_like(ccfft), where=denom != 0)
    corr = np.fft.ifft2(pcfft).real
    if zero_origin:
        corr[0, 0] = 0.0
    return corr


def correlate_shift(
    image1: np.ndarray,
    image2: np.ndarray,
    *,
    correlation_type: CorrelationType = "phase",
    subpixel_window: int = 5,
) -> ShiftResult:
    """Measure the wrapped pixel shift between two images.

    This is the standalone replacement for Leginon's
    ``measureScopeChange`` correlation-and-peak section.  Binning and camera
    bookkeeping are deliberately left to the caller.
    """

    if correlation_type == "phase":
        corr = phase_correlate(image1, image2)
    elif correlation_type == "cross":
        corr = cross_correlate(image1, image2)
    else:
        raise ValueError("correlation_type must be 'phase' or 'cross'")

    peak, peak_value, snr = subpixel_peak(corr, npix=subpixel_window)
    return ShiftResult(
        shift=wrap_coord(peak, corr.shape),
        peak=peak,
        peak_value=peak_value,
        correlation=corr,
        snr=snr,
    )


def wrap_coord(coord: Tuple[float, float], shape: Tuple[int, int]) -> Tuple[float, float]:
    """Convert an unsigned correlation peak coordinate to a signed shift."""

    row, col = coord
    row_shift = row if row < shape[0] / 2.0 else row - shape[0]
    col_shift = col if col < shape[1] / 2.0 else col - shape[1]
    return (float(row_shift), float(col_shift))


def subpixel_peak(image: np.ndarray, *, npix: int = 5) -> Tuple[Tuple[float, float], float, float]:
    """Find a peak and refine it by fitting a separable 2-D quadratic."""

    if npix < 3 or npix % 2 == 0:
        raise ValueError("npix must be an odd integer >= 3")
    array = np.asarray(image, dtype=np.float64)
    pixel_index = int(np.argmax(array.ravel()))
    peak_value = float(array.flat[pixel_index])
    peak_row, peak_col = np.unravel_index(pixel_index, array.shape)

    roi = _crop_wrap(array, (peak_row, peak_col), (npix, npix))
    try:
        row_offset, col_offset, fitted_value = _quadratic_peak(roi)
    except (np.linalg.LinAlgError, FloatingPointError, ZeroDivisionError, ValueError):
        row_offset = col_offset = npix // 2
        fitted_value = peak_value

    if not (0.0 <= row_offset <= npix):
        row_offset = npix // 2
    if not (0.0 <= col_offset <= npix):
        col_offset = npix // 2

    half = npix // 2
    sub_row = float(peak_row + row_offset - half)
    sub_col = float(peak_col + col_offset - half)
    sub_row %= array.shape[0]
    sub_col %= array.shape[1]

    noise = float(np.std(array))
    mean = float(np.mean(array))
    snr = float((peak_value - mean) / noise) if noise != 0.0 else peak_value
    return (sub_row, sub_col), float(fitted_value), snr


def _quadratic_peak(array: np.ndarray) -> Tuple[float, float, float]:
    rows, cols = array.shape
    design = np.zeros((rows * cols, 5), dtype=np.float64)
    values = np.zeros((rows * cols,), dtype=np.float64)
    i = 0
    for row in range(rows):
        for col in range(cols):
            design[i] = (row * row, row, col * col, col, 1.0)
            values[i] = array[row, col]
            i += 1

    coeffs, *_ = np.linalg.lstsq(design, values, rcond=None)
    row0 = -coeffs[1] / (2.0 * coeffs[0])
    col0 = -coeffs[3] / (2.0 * coeffs[2])
    if not np.isfinite(row0) or not np.isfinite(col0):
        raise ValueError("quadratic fit produced a non-finite peak")
    value = coeffs[0] * row0**2 + coeffs[1] * row0 + coeffs[2] * col0**2 + coeffs[3] * col0 + coeffs[4]
    return float(row0), float(col0), float(value)


def _crop_wrap(array: np.ndarray, center: Tuple[int, int], shape: Tuple[int, int]) -> np.ndarray:
    half_rows = shape[0] // 2
    half_cols = shape[1] // 2
    row_indices = (np.arange(shape[0]) + center[0] - half_rows) % array.shape[0]
    col_indices = (np.arange(shape[1]) + center[1] - half_cols) % array.shape[1]
    return array[np.ix_(row_indices, col_indices)]


def _validated_pair(image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    im1 = np.asarray(image1, dtype=np.float64)
    im2 = np.asarray(image2, dtype=np.float64)
    if im1.shape != im2.shape:
        raise ValueError(f"images must have the same shape, got {im1.shape} and {im2.shape}")
    if im1.ndim != 2:
        raise ValueError("images must be two-dimensional arrays")
    return im1, im2

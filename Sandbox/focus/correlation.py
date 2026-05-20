"""Image correlation helpers used by the focus algorithms.

The implementation follows the numerical behavior of Leginon's
``pyami.correlator`` and ``pyami.peakfinder`` in a standalone form, with
SerialEM-style edge tapering and padding so that non-periodic micrographs
do not produce spurious wrap-around correlation.
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
    peak_ratio: float
    normalized_ccc: float


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
    taper_fraction: float = 0.1,
    pad_fraction: float = 0.0,
    lowpass: float = 0.0,
    zero_origin: bool = False,
) -> ShiftResult:
    """Measure the wrapped pixel shift between two images.

    This is the standalone replacement for Leginon's
    ``measureScopeChange`` correlation-and-peak section.  Binning and camera
    bookkeeping are deliberately left to the caller.

    ``taper_fraction`` applies a raised-cosine edge taper to each image before
    the FFT so that a non-periodic micrograph does not produce a strong
    spurious correlation along the wrap boundary.  ``pad_fraction`` zero-pads
    the tapered images, which keeps a large genuine shift from aliasing past
    the wrap boundary.  ``lowpass`` Gaussian-smooths the correlation map, the
    standalone equivalent of Leginon's ``measureScopeChange`` ``lp`` argument.

    ``zero_origin`` blanks the phase-correlation origin pixel.  It defaults to
    false because near-zero shift is a valid focus result; enable it only when
    the caller knows a zero-shift peak must be an artifact.
    """

    im1, im2 = _validated_pair(image1, image2)
    _validate_preprocess_args(taper_fraction, pad_fraction, lowpass)
    pre1 = _preprocess(im1, taper_fraction, pad_fraction)
    pre2 = _preprocess(im2, taper_fraction, pad_fraction)

    if correlation_type == "phase":
        corr = phase_correlate(pre1, pre2, zero_origin=zero_origin)
    elif correlation_type == "cross":
        corr = cross_correlate(pre1, pre2)
    else:
        raise ValueError("correlation_type must be 'phase' or 'cross'")

    if lowpass > 0.0:
        corr = _gaussian_blur(corr, lowpass)

    peak, peak_value, snr = subpixel_peak(corr, npix=subpixel_window)
    shift = wrap_coord(peak, corr.shape)
    return ShiftResult(
        shift=shift,
        peak=peak,
        peak_value=peak_value,
        correlation=corr,
        snr=snr,
        peak_ratio=_peak_ratio(corr, int(round(peak[0])), int(round(peak[1])), subpixel_window),
        normalized_ccc=_normalized_ccc(pre1, pre2, shift),
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

    snr = _peak_snr(array, int(peak_row), int(peak_col), peak_value, npix)
    return (sub_row, sub_col), float(fitted_value), snr


def _peak_snr(
    array: np.ndarray,
    peak_row: int,
    peak_col: int,
    peak_value: float,
    npix: int,
) -> float:
    """Estimate peak SNR with the peak and its sidelobes excluded.

    Including the peak in the noise estimate inflates the standard deviation
    and understates the SNR, so the background statistics are taken from
    everything outside a wrapped window centred on the peak.
    """

    exclude = 2 * npix + 1
    half = exclude // 2
    rows = (np.arange(exclude) + peak_row - half) % array.shape[0]
    cols = (np.arange(exclude) + peak_col - half) % array.shape[1]
    mask = np.ones(array.shape, dtype=bool)
    mask[np.ix_(rows, cols)] = False
    background = array[mask]
    if background.size == 0:
        return peak_value
    noise = float(np.std(background))
    mean = float(np.mean(background))
    return float((peak_value - mean) / noise) if noise != 0.0 else peak_value


def _preprocess(image: np.ndarray, taper_fraction: float, pad_fraction: float) -> np.ndarray:
    """Mean-subtract, edge-taper, and optionally zero-pad an image for FFT."""

    array = image - float(np.mean(image))
    if taper_fraction > 0.0:
        array = array * _edge_mask(array.shape, taper_fraction)
    if pad_fraction > 0.0:
        pad_rows = int(round(pad_fraction * array.shape[0]))
        pad_cols = int(round(pad_fraction * array.shape[1]))
        array = np.pad(array, ((0, pad_rows), (0, pad_cols)), mode="constant")
    return array


def _validate_preprocess_args(taper_fraction: float, pad_fraction: float, lowpass: float) -> None:
    if not np.all(np.isfinite((taper_fraction, pad_fraction, lowpass))):
        raise ValueError("taper_fraction, pad_fraction, and lowpass must be finite")
    if taper_fraction < 0.0 or taper_fraction > 0.5:
        raise ValueError("taper_fraction must be in [0.0, 0.5]")
    if pad_fraction < 0.0:
        raise ValueError("pad_fraction must be non-negative")
    if lowpass < 0.0:
        raise ValueError("lowpass must be non-negative")


def _peak_ratio(array: np.ndarray, peak_row: int, peak_col: int, npix: int) -> float:
    """Return primary peak divided by strongest background peak."""

    peak_row %= array.shape[0]
    peak_col %= array.shape[1]
    exclude = 2 * npix + 1
    half = exclude // 2
    rows = (np.arange(exclude) + peak_row - half) % array.shape[0]
    cols = (np.arange(exclude) + peak_col - half) % array.shape[1]
    mask = np.ones(array.shape, dtype=bool)
    mask[np.ix_(rows, cols)] = False
    background = array[mask]
    if background.size == 0:
        return float("inf")
    second = max(float(np.max(background)), 0.0)
    peak = float(array[peak_row, peak_col])
    if second == 0.0:
        return float("inf") if peak > 0.0 else 0.0
    return peak / second


def _normalized_ccc(image1: np.ndarray, image2: np.ndarray, shift: Tuple[float, float]) -> float:
    """Return an approximate normalized cross-correlation coefficient.

    The measured shift is applied with an integer ``np.roll``, so the value is a
    coarse quality score, not an exact CCC: sub-pixel shift is ignored and the
    rolled-in wrap region (plus any zero padding) mismatches content, biasing
    the result low.  It is intended only for threshold gating.
    """

    row_shift = int(round(shift[0]))
    col_shift = int(round(shift[1]))
    aligned = np.roll(np.roll(image1, -row_shift, axis=0), -col_shift, axis=1)
    a = aligned - float(np.mean(aligned))
    b = image2 - float(np.mean(image2))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.sum(a * b) / denom)


def _edge_mask(shape: Tuple[int, int], taper_fraction: float) -> np.ndarray:
    """Return a separable raised-cosine (Tukey) edge mask for ``shape``.

    ``taper_fraction`` is already range-checked by ``_validate_preprocess_args``
    before this is reached.
    """

    row_window = _tukey_window(shape[0], taper_fraction)
    col_window = _tukey_window(shape[1], taper_fraction)
    return np.outer(row_window, col_window)


def _tukey_window(length: int, taper_fraction: float) -> np.ndarray:
    """Return a 1-D Tukey window: flat centre, raised-cosine ramps at the ends."""

    window = np.ones(length, dtype=np.float64)
    edge = int(round(taper_fraction * length))
    if edge < 1:
        return window
    ramp = 0.5 * (1.0 - np.cos(np.pi * (np.arange(edge) + 0.5) / edge))
    window[:edge] = ramp
    window[length - edge:] = ramp[::-1]
    return window


def _gaussian_blur(array: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian-smooth a real array via a frequency-domain multiply."""

    rows, cols = array.shape
    freq_rows = np.fft.fftfreq(rows)
    freq_cols = np.fft.fftfreq(cols)
    kernel_rows = np.exp(-2.0 * (np.pi * sigma * freq_rows) ** 2)
    kernel_cols = np.exp(-2.0 * (np.pi * sigma * freq_cols) ** 2)
    kernel = np.outer(kernel_rows, kernel_cols)
    return np.fft.ifft2(np.fft.fft2(array) * kernel).real


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

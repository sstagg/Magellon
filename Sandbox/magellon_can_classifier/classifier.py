from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy import ndimage
from scipy import fft as sp_fft

try:
    from skimage.registration import phase_cross_correlation as _phase_xcorr_subpixel
except Exception:
    _phase_xcorr_subpixel = None

try:
    from skimage.transform import warp_polar as _warp_polar
except Exception:
    _warp_polar = None

try:
    import torch
except Exception:
    torch = None


def _normalize_image(img: np.ndarray) -> np.ndarray:
    mean = float(img.mean())
    std = float(img.std())
    if std <= 1e-8:
        return (img - mean).astype(np.float32)
    return ((img - mean) / std).astype(np.float32)


def _make_circular_mask(shape_yx: tuple[int, int], diameter_px: float, soft_edge_frac: float = 0.15) -> np.ndarray:
    h, w = int(shape_yx[0]), int(shape_yx[1])
    yy, xx = np.indices((h, w), dtype=np.float32)
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    radius = max(0.0, float(diameter_px) / 2.0)
    if radius <= 1e-6:
        return np.zeros((h, w), dtype=np.float32)
    edge = max(1.0, float(soft_edge_frac) * radius)
    inner = max(0.0, radius - edge)
    mask = np.zeros((h, w), dtype=np.float32)
    inside = rr <= inner
    trans = (rr > inner) & (rr < radius)
    mask[inside] = 1.0
    # Raised-cosine rolloff from inner->radius.
    x = (rr[trans] - inner) / max(1e-6, (radius - inner))
    mask[trans] = 0.5 * (1.0 + np.cos(np.pi * x))
    return mask.astype(np.float32)


def _apply_circular_mask_stack(stack: np.ndarray, diameter_px: float) -> np.ndarray:
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    mask = _make_circular_mask((int(stack.shape[1]), int(stack.shape[2])), diameter_px=diameter_px)
    return (stack * mask[None, :, :]).astype(np.float32)


def _center_image_moment(img: np.ndarray, max_shift_frac: float = 0.05) -> np.ndarray:
    """
    Projection-moment centering.
    """
    proc = _normalize_image(img).copy()
    proc[proc < 0] = 0
    h, w = proc.shape
    x_profile = proc.sum(axis=0)
    y_profile = proc.sum(axis=1)
    sx = float(x_profile.sum())
    sy = float(y_profile.sum())
    if sx <= 0 or sy <= 0:
        return img.astype(np.float32)
    x_coords = np.arange(w, dtype=np.float32)
    y_coords = np.arange(h, dtype=np.float32)
    cx = float((x_profile * x_coords).sum() / sx)
    cy = float((y_profile * y_coords).sum() / sy)
    dy = h / 2.0 - cy
    dx = w / 2.0 - cx
    max_dy = max_shift_frac * h / 2.0
    max_dx = max_shift_frac * w / 2.0
    dy = math.copysign(min(abs(dy), max_dy), dy)
    dx = math.copysign(min(abs(dx), max_dx), dx)
    return ndimage.shift(img, shift=(dy, dx), order=1, mode="wrap").astype(np.float32)


def _center_image_com(img: np.ndarray, max_shift_frac: float = 0.25) -> np.ndarray:
    """
    Center image by intensity center-of-mass with shift clipping for stability.
    """
    arr = np.asarray(img, dtype=np.float32)
    # Polarity-agnostic weighting: emphasize deviations from background level.
    bg = float(np.median(arr))
    w = np.abs(arr - bg)
    s = float(w.sum())
    if s <= 1e-8:
        return arr.astype(np.float32)
    cy, cx = ndimage.center_of_mass(w)
    if not np.isfinite(cy) or not np.isfinite(cx):
        return arr.astype(np.float32)
    h, ww = arr.shape
    dy = (h - 1) / 2.0 - float(cy)
    dx = (ww - 1) / 2.0 - float(cx)
    max_dy = float(max_shift_frac) * h / 2.0
    max_dx = float(max_shift_frac) * ww / 2.0
    dy = math.copysign(min(abs(dy), max_dy), dy)
    dx = math.copysign(min(abs(dx), max_dx), dx)
    return ndimage.shift(arr, shift=(dy, dx), order=1, mode="constant", cval=bg).astype(np.float32)


def _center_stack_com(stack: np.ndarray, max_shift_frac: float = 0.25) -> np.ndarray:
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    return np.stack([_center_image_com(stack[i], max_shift_frac=max_shift_frac) for i in range(stack.shape[0])]).astype(np.float32)


def _com_shift(img: np.ndarray, max_shift_frac: float = 0.25) -> tuple[float, float]:
    arr = np.asarray(img, dtype=np.float32)
    # Polarity-agnostic weighting: emphasize deviations from background level.
    bg = float(np.median(arr))
    w = np.abs(arr - bg)
    s = float(w.sum())
    if s <= 1e-8:
        return 0.0, 0.0
    cy, cx = ndimage.center_of_mass(w)
    if not np.isfinite(cy) or not np.isfinite(cx):
        return 0.0, 0.0
    h, ww = arr.shape
    dy = (h - 1) / 2.0 - float(cy)
    dx = (ww - 1) / 2.0 - float(cx)
    max_dy = float(max_shift_frac) * h / 2.0
    max_dx = float(max_shift_frac) * ww / 2.0
    dy = math.copysign(min(abs(dy), max_dy), dy)
    dx = math.copysign(min(abs(dx), max_dx), dx)
    return float(dy), float(dx)


def _weight_sum(img: np.ndarray) -> float:
    arr = np.asarray(img, dtype=np.float32)
    bg = float(np.median(arr))
    return float(np.abs(arr - bg).sum())


def _center_stack_com_mask_guided(
    measurement_stack: np.ndarray,
    target_stack: np.ndarray,
    max_shift_frac: float = 0.25,
) -> np.ndarray:
    """
    Estimate COM shifts from measurement_stack, apply shifts to target_stack.
    Used for masked-COM guidance while preserving unmasked signal during shifting.
    """
    if measurement_stack.ndim != 3 or target_stack.ndim != 3:
        raise ValueError("stacks must be 3D [n, y, x]")
    if measurement_stack.shape != target_stack.shape:
        raise ValueError("measurement_stack and target_stack must have same shape")
    out = np.zeros_like(target_stack, dtype=np.float32)
    for i in range(target_stack.shape[0]):
        # Fallback to unmasked shift if masked measurement has too little usable signal.
        meas_w = _weight_sum(measurement_stack[i])
        targ_w = _weight_sum(target_stack[i])
        use_fallback = (targ_w > 1e-8) and (meas_w / targ_w < 0.05)
        dy, dx = _com_shift(target_stack[i], max_shift_frac=max_shift_frac) if use_fallback else _com_shift(
            measurement_stack[i], max_shift_frac=max_shift_frac
        )
        bg = float(np.median(target_stack[i]))
        out[i] = ndimage.shift(target_stack[i], shift=(dy, dx), order=1, mode="constant", cval=bg).astype(np.float32)
    return out


def _com_shift_stats(measurement_stack: np.ndarray, target_stack: np.ndarray | None = None) -> tuple[float, float, float]:
    if measurement_stack.ndim != 3:
        return 0.0, 0.0, 0.0
    mags = []
    if target_stack is None:
        for i in range(measurement_stack.shape[0]):
            dy, dx = _com_shift(measurement_stack[i])
            mags.append(float(math.hypot(dy, dx)))
    else:
        for i in range(measurement_stack.shape[0]):
            meas_w = _weight_sum(measurement_stack[i])
            targ_w = _weight_sum(target_stack[i])
            use_fallback = (targ_w > 1e-8) and (meas_w / targ_w < 0.05)
            dy, dx = _com_shift(target_stack[i]) if use_fallback else _com_shift(measurement_stack[i])
            mags.append(float(math.hypot(dy, dx)))
    if not mags:
        return 0.0, 0.0, 0.0
    arr = np.asarray(mags, dtype=np.float32)
    return float(arr.mean()), float(np.median(arr)), float(arr.max())


def _estimate_phase_shift(ref: np.ndarray, img: np.ndarray) -> tuple[float, float]:
    if _phase_xcorr_subpixel is not None:
        shift, _error, _phase = _phase_xcorr_subpixel(ref, img, upsample_factor=10, normalization=None)
        return float(shift[0]), float(shift[1])
    return _phase_corr_shift_integer(ref, img)


def _rotational_average_image(img: np.ndarray) -> np.ndarray:
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape
    yy, xx = np.indices((h, w), dtype=np.float32)
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rbin = np.floor(rr).astype(np.int32)
    max_r = int(rbin.max())
    flat_r = rbin.ravel()
    flat_v = arr.ravel().astype(np.float32)
    sums = np.bincount(flat_r, weights=flat_v, minlength=max_r + 1).astype(np.float32)
    counts = np.bincount(flat_r, minlength=max_r + 1).astype(np.float32)
    prof = np.zeros_like(sums, dtype=np.float32)
    nz = counts > 0
    prof[nz] = sums[nz] / counts[nz]
    ravg = np.interp(rr.ravel(), np.arange(max_r + 1, dtype=np.float32), prof).reshape(h, w)
    return ravg.astype(np.float32)


def _center_stack_to_rotavg_phasecorr(
    stack: np.ndarray, return_shifts: bool = False
) -> tuple[np.ndarray, np.ndarray, tuple[float, float, float]] | tuple[np.ndarray, np.ndarray, tuple[float, float, float], np.ndarray]:
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    mean_avg = np.mean(np.asarray(stack, dtype=np.float32), axis=0).astype(np.float32)
    rot_ref = _normalize_image(_rotational_average_image(mean_avg))
    out = np.zeros_like(stack, dtype=np.float32)
    shifts = np.zeros((stack.shape[0], 2), dtype=np.float32)
    mags: list[float] = []
    for i in range(stack.shape[0]):
        img = np.asarray(stack[i], dtype=np.float32)
        dy, dx = _estimate_phase_shift(rot_ref, _normalize_image(img))
        shifts[i, 0] = float(dy)
        shifts[i, 1] = float(dx)
        mags.append(float(math.hypot(dy, dx)))
        out[i] = ndimage.shift(img, shift=(dy, dx), order=1, mode="constant", cval=float(np.median(img))).astype(np.float32)
    if mags:
        arr = np.asarray(mags, dtype=np.float32)
        stats = (float(arr.mean()), float(np.median(arr)), float(arr.max()))
    else:
        stats = (0.0, 0.0, 0.0)
    if return_shifts:
        return out.astype(np.float32), rot_ref.astype(np.float32), stats, shifts
    return out.astype(np.float32), rot_ref.astype(np.float32), stats


def _stack_averages_by_assignment(stack: np.ndarray, assign: np.ndarray, n_classes: int) -> tuple[np.ndarray, np.ndarray]:
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n,y,x]")
    n = int(stack.shape[0])
    if int(assign.size) != n:
        raise ValueError("assignment size must match stack particle count")
    h, w = int(stack.shape[1]), int(stack.shape[2])
    k = int(n_classes)
    avgs = np.zeros((k, h, w), dtype=np.float32)
    counts = np.zeros((k,), dtype=np.int32)
    for i in range(n):
        c = int(assign[i])
        if c < 0 or c >= k:
            continue
        avgs[c] += stack[i]
        counts[c] += 1
    for c in range(k):
        if counts[c] > 0:
            avgs[c] /= float(counts[c])
    return avgs.astype(np.float32), counts.astype(np.int32)


def class_half_averages(
    stack: np.ndarray,
    assignments: np.ndarray,
    n_classes: int,
    n_threads: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n,y,x]")
    n = int(stack.shape[0])
    if assignments.size != n:
        raise ValueError("assignments length must match stack particle count")
    k = int(n_classes)
    h, w = int(stack.shape[1]), int(stack.shape[2])
    sum_all = np.zeros((k, h, w), dtype=np.float32)
    sum_h1 = np.zeros((k, h, w), dtype=np.float32)
    sum_h2 = np.zeros((k, h, w), dtype=np.float32)
    cnt_all = np.zeros((k,), dtype=np.int32)
    cnt_h1 = np.zeros((k,), dtype=np.int32)
    cnt_h2 = np.zeros((k,), dtype=np.int32)

    class_indices: list[np.ndarray] = []
    for c in range(k):
        idx = np.where(assignments == c)[0].astype(np.int32)
        class_indices.append(idx)

    def _acc_class(c: int) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, int, int, int]:
        idx = class_indices[c]
        if idx.size == 0:
            z = np.zeros((h, w), dtype=np.float32)
            return c, z, z, z, 0, 0, 0
        cls = np.asarray(stack[idx], dtype=np.float32)
        all_sum = cls.sum(axis=0, dtype=np.float32)
        cnta = int(idx.size)
        idx_h1 = idx[::2]
        idx_h2 = idx[1::2]
        h1 = np.asarray(stack[idx_h1], dtype=np.float32)
        h2 = np.asarray(stack[idx_h2], dtype=np.float32)
        h1_sum = h1.sum(axis=0, dtype=np.float32) if idx_h1.size > 0 else np.zeros((h, w), dtype=np.float32)
        h2_sum = h2.sum(axis=0, dtype=np.float32) if idx_h2.size > 0 else np.zeros((h, w), dtype=np.float32)
        return c, all_sum, h1_sum, h2_sum, cnta, int(idx_h1.size), int(idx_h2.size)

    if int(n_threads) <= 1 or k <= 1:
        for c in range(k):
            c0, all_sum, h1_sum, h2_sum, cnta, c1, c2 = _acc_class(c)
            sum_all[c0] = all_sum
            sum_h1[c0] = h1_sum
            sum_h2[c0] = h2_sum
            cnt_all[c0] = cnta
            cnt_h1[c0] = c1
            cnt_h2[c0] = c2
    else:
        with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
            for c0, all_sum, h1_sum, h2_sum, cnta, c1, c2 in ex.map(_acc_class, range(k)):
                sum_all[c0] = all_sum
                sum_h1[c0] = h1_sum
                sum_h2[c0] = h2_sum
                cnt_all[c0] = cnta
                cnt_h1[c0] = c1
                cnt_h2[c0] = c2
    avg_all = np.zeros_like(sum_all, dtype=np.float32)
    avg_h1 = np.zeros_like(sum_h1, dtype=np.float32)
    avg_h2 = np.zeros_like(sum_h2, dtype=np.float32)
    for c in range(k):
        if cnt_all[c] > 0:
            avg_all[c] = sum_all[c] / float(cnt_all[c])
        if cnt_h1[c] > 0:
            avg_h1[c] = sum_h1[c] / float(cnt_h1[c])
        if cnt_h2[c] > 0:
            avg_h2[c] = sum_h2[c] / float(cnt_h2[c])
    return avg_all, cnt_all, avg_h1, avg_h2, np.stack([cnt_h1, cnt_h2], axis=1).astype(np.int32)


def make_replayed_class_averages_with_halves(
    source_stack: np.ndarray,
    assignments: np.ndarray,
    rotations_deg: np.ndarray,
    shifts_lowres_px: np.ndarray,
    fft_scale: float,
    n_classes: int,
    n_threads: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if source_stack.ndim != 3:
        raise ValueError("source_stack must be 3D [n,y,x]")
    n = int(source_stack.shape[0])
    if assignments.size != n or rotations_deg.size != n or shifts_lowres_px.shape[0] != n:
        raise ValueError("assignment/rotation/shift lengths must match particle count")
    transformed = np.zeros_like(source_stack, dtype=np.float32)
    inv_scale = 1.0 / float(fft_scale) if abs(float(fft_scale)) > 1e-12 else 1.0
    for i in range(n):
        img = np.asarray(source_stack[i], dtype=np.float32)
        ang = float(rotations_deg[i])
        rot = ndimage.rotate(img, ang, reshape=False, order=1, mode="wrap")
        dy = float(shifts_lowres_px[i, 0]) * inv_scale
        dx = float(shifts_lowres_px[i, 1]) * inv_scale
        transformed[i] = ndimage.shift(
            rot, shift=(dy, dx), order=1, mode="constant", cval=float(np.median(rot))
        ).astype(np.float32)
    return class_half_averages(transformed, assignments, n_classes=n_classes, n_threads=n_threads)


def replay_mra_transforms_and_average_with_halves(
    source_stack: np.ndarray,
    assignments: np.ndarray,
    iteration_rotations: Sequence[np.ndarray],
    iteration_shifts: Sequence[np.ndarray],
    fft_scale: float,
    n_classes: int,
    n_threads: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Replay all per-iteration MRA transforms in sequence onto source_stack, then
    compute class averages and odd/even half-averages by final assignments.
    """
    if source_stack.ndim != 3:
        raise ValueError("source_stack must be 3D [n,y,x]")
    n = int(source_stack.shape[0])
    if assignments.size != n:
        raise ValueError("assignments length must match particle count")
    if len(iteration_rotations) != len(iteration_shifts):
        raise ValueError("iteration_rotations and iteration_shifts length mismatch")
    inv_scale = 1.0 / float(fft_scale) if abs(float(fft_scale)) > 1e-12 else 1.0
    transformed = np.asarray(source_stack, dtype=np.float32).copy()
    for rots, sh in zip(iteration_rotations, iteration_shifts):
        r = np.asarray(rots, dtype=np.float32)
        s = np.asarray(sh, dtype=np.float32)
        if r.size != n or s.shape != (n, 2):
            raise ValueError("iteration transform shape mismatch")
        for i in range(n):
            img = transformed[i]
            ang = float(r[i])
            tmp = ndimage.rotate(img, ang, reshape=False, order=1, mode="wrap")
            dy = float(s[i, 0]) * inv_scale
            dx = float(s[i, 1]) * inv_scale
            transformed[i] = ndimage.shift(
                tmp, shift=(dy, dx), order=1, mode="constant", cval=float(np.median(tmp))
            ).astype(np.float32)
    return class_half_averages(transformed, assignments, n_classes=n_classes, n_threads=n_threads)


def frc_curve(img1: np.ndarray, img2: np.ndarray, apix: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a = np.asarray(img1, dtype=np.float32)
    b = np.asarray(img2, dtype=np.float32)
    if a.shape != b.shape:
        raise ValueError("FRC image shapes must match")
    h, w = int(a.shape[0]), int(a.shape[1])
    f1 = np.fft.fftshift(np.fft.fft2(a))
    f2 = np.fft.fftshift(np.fft.fft2(b))
    yy, xx = np.indices((h, w), dtype=np.float32)
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rbin = np.floor(rr).astype(np.int32)
    max_r = int(min(h, w) // 2)
    frc_vals = []
    freq_vals = []
    n_eff = float(min(h, w))
    for r in range(1, max_r + 1):
        m = rbin == r
        if not np.any(m):
            continue
        aa = f1[m]
        bb = f2[m]
        num = np.sum(aa * np.conjugate(bb))
        den = np.sqrt(np.sum(np.abs(aa) ** 2) * np.sum(np.abs(bb) ** 2))
        frc = float(np.real(num) / np.real(den)) if np.real(den) > 1e-12 else 0.0
        freq = float(r / (n_eff * float(apix)))  # cycles/Angstrom
        frc_vals.append(frc)
        freq_vals.append(freq)
    freq = np.asarray(freq_vals, dtype=np.float32)
    frc = np.asarray(frc_vals, dtype=np.float32)
    res = np.where(freq > 1e-12, 1.0 / freq, np.inf).astype(np.float32)
    return freq, res, frc


def frc_resolution(freq: np.ndarray, frc: np.ndarray, threshold: float) -> float | None:
    if freq.size < 2 or frc.size != freq.size:
        return None
    for i in range(1, frc.size):
        y0 = float(frc[i - 1])
        y1 = float(frc[i])
        if y0 >= threshold and y1 <= threshold:
            x0 = float(freq[i - 1])
            x1 = float(freq[i])
            if abs(y1 - y0) < 1e-8:
                fx = x1
            else:
                t = (threshold - y0) / (y1 - y0)
                fx = x0 + t * (x1 - x0)
            if fx <= 1e-12:
                return None
            return float(1.0 / fx)
    return None


def _lowpass_gaussian(image: np.ndarray, apix: float, resolution_angstrom: float | None) -> np.ndarray:
    if resolution_angstrom is None:
        return image
    resolution = float(resolution_angstrom)
    if resolution <= 0 or apix <= 0:
        raise ValueError("lowpass resolution and apix must be > 0")
    sigma_pixels = 0.187 * resolution / float(apix)
    if sigma_pixels <= 0:
        return image
    return ndimage.gaussian_filter(image, sigma=sigma_pixels).astype(np.float32)


def _fft_scale_image(image: np.ndarray, scale: float) -> np.ndarray:
    """
    Fourier-domain resampling by symmetric crop/pad in centered FFT space.
    """
    s = float(scale)
    if s <= 0:
        raise ValueError("fft_scale must be > 0")
    if abs(s - 1.0) < 1e-8:
        return image.astype(np.float32)
    h, w = int(image.shape[0]), int(image.shape[1])
    new_h = max(8, int(round(h * s)))
    new_w = max(8, int(round(w * s)))
    f = np.fft.fftshift(np.fft.fft2(image))
    out_f = np.zeros((new_h, new_w), dtype=np.complex64)

    src_y0 = max(0, (h - new_h) // 2)
    src_x0 = max(0, (w - new_w) // 2)
    dst_y0 = max(0, (new_h - h) // 2)
    dst_x0 = max(0, (new_w - w) // 2)
    copy_h = min(h, new_h)
    copy_w = min(w, new_w)
    out_f[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = f[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]

    # Energy-preserving scale factor for FFT resize.
    amp = (float(new_h) * float(new_w)) / max(1.0, float(h) * float(w))
    out = np.fft.ifft2(np.fft.ifftshift(out_f)).real * amp
    return out.astype(np.float32)


def _electron_wavelength_angstrom(voltage_kv: float) -> float:
    # Relativistic electron wavelength in Angstroms.
    v = float(voltage_kv) * 1000.0
    return 12.2639 / math.sqrt(v * (1.0 + 0.97845e-6 * v))


def _ctf_phase_flip_image(
    image: np.ndarray,
    apix: float,
    defocus_um: float,
    voltage_kv: float,
    cs_mm: float,
    amp_contrast: float,
) -> np.ndarray:
    h, w = image.shape
    fy = np.fft.fftfreq(h, d=apix)
    fx = np.fft.fftfreq(w, d=apix)
    yy, xx = np.meshgrid(fy, fx, indexing="ij")
    s2 = xx * xx + yy * yy
    s4 = s2 * s2

    lam = _electron_wavelength_angstrom(voltage_kv)
    cs_ang = float(cs_mm) * 1.0e7
    defocus_ang = float(defocus_um) * 1.0e4
    wac = float(amp_contrast)
    wac = min(max(wac, 0.0), 0.99)
    wpc = math.sqrt(max(0.0, 1.0 - wac * wac))

    # Match EMAN phase-flip sign convention:
    #   gamma = (pi/2)*Cs*lambda^3*s^4 - pi*defocus*lambda*s^2
    #   acac  = atan(wgh / sqrt(1-wgh^2)), where wgh == amp_contrast
    #   CTF_SIGN = sign(cos(gamma - acac))
    gamma = 0.5 * math.pi * cs_ang * (lam ** 3) * s4 - math.pi * lam * defocus_ang * s2
    acac = math.atan2(wac, wpc)
    sign = np.where(np.cos(gamma - acac) >= 0.0, 1.0, -1.0).astype(np.float32)  # bool mask converted to 1,-1 array for phase-flip
    fft_im = np.fft.fft2(image)
    corrected = np.fft.ifft2(fft_im * sign).real
    return corrected.astype(np.float32)


def _phase_flip_stack(
    stack: np.ndarray,
    apix: float,
    defocus_um: float | Sequence[float],
    voltage_kv: float,
    cs_mm: float,
    amp_contrast: float,
    n_threads: int = 1,
) -> np.ndarray:
    n = stack.shape[0]
    if np.isscalar(defocus_um):
        defocus_list = np.full((n,), float(defocus_um), dtype=np.float32)
    else:
        defocus_list = np.asarray(defocus_um, dtype=np.float32)
        if defocus_list.size != n:
            raise ValueError("defocus_um sequence length must match number of particles")
    if int(n_threads) <= 1:
        out = np.zeros_like(stack, dtype=np.float32)
        for i in range(n):
            out[i] = _ctf_phase_flip_image(
                image=stack[i],
                apix=apix,
                defocus_um=float(defocus_list[i]),
                voltage_kv=voltage_kv,
                cs_mm=cs_mm,
                amp_contrast=amp_contrast,
            )
        return out

    def _one(i: int) -> np.ndarray:
        return _ctf_phase_flip_image(
            image=stack[i],
            apix=apix,
            defocus_um=float(defocus_list[i]),
            voltage_kv=voltage_kv,
            cs_mm=cs_mm,
            amp_contrast=amp_contrast,
        )

    with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
        return np.stack(list(ex.map(_one, range(n)))).astype(np.float32)


def preprocess_stack(
    stack: np.ndarray,
    apix: float,
    fft_scale: float = 1.0,
    lowpass_resolution: float | None = None,
    invert: bool = False,
    center: bool = True,
    normalize: bool = True,
    phase_flip_ctf: bool = False,
    ctf_defocus_um: float | Sequence[float] | None = None,
    ctf_voltage_kv: float = 300.0,
    ctf_cs_mm: float = 2.7,
    ctf_amp_contrast: float = 0.1,
    n_threads: int = 1,
) -> np.ndarray:
    out = np.asarray(stack, dtype=np.float32).copy()
    if out.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    current_apix = float(apix)
    if invert:
        out *= -1.0
    if phase_flip_ctf:
        if ctf_defocus_um is None:
            raise ValueError("ctf_defocus_um is required when phase_flip_ctf=True")
        out = _phase_flip_stack(
            stack=out,
            apix=current_apix,
            defocus_um=ctf_defocus_um,
            voltage_kv=ctf_voltage_kv,
            cs_mm=ctf_cs_mm,
            amp_contrast=ctf_amp_contrast,
            n_threads=n_threads,
        )
    if abs(float(fft_scale) - 1.0) > 1e-8:
        if int(n_threads) <= 1:
            out = np.stack([_fft_scale_image(out[i], fft_scale) for i in range(out.shape[0])])
        else:
            with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
                out = np.stack(list(ex.map(lambda i: _fft_scale_image(out[i], fft_scale), range(out.shape[0]))))
        # s_new = s_old / fft_scale, so apix_new = apix_old / fft_scale.
        current_apix = current_apix / float(fft_scale)
    if lowpass_resolution is not None:
        if int(n_threads) <= 1:
            out = np.stack([_lowpass_gaussian(out[i], current_apix, lowpass_resolution) for i in range(out.shape[0])])
        else:
            with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
                out = np.stack(
                    list(ex.map(lambda i: _lowpass_gaussian(out[i], current_apix, lowpass_resolution), range(out.shape[0])))
                )
    if center:
        if int(n_threads) <= 1:
            out = np.stack([_center_image_moment(out[i]) for i in range(out.shape[0])])
        else:
            with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
                out = np.stack(list(ex.map(lambda i: _center_image_moment(out[i]), range(out.shape[0]))))
    if normalize:
        if int(n_threads) <= 1:
            out = np.stack([_normalize_image(out[i]) for i in range(out.shape[0])])
        else:
            with ThreadPoolExecutor(max_workers=int(n_threads)) as ex:
                out = np.stack(list(ex.map(lambda i: _normalize_image(out[i]), range(out.shape[0]))))
    return out.astype(np.float32)


def _cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    aa = float(np.sqrt((a * a).sum()))
    bb = float(np.sqrt((b * b).sum()))
    if aa <= 1e-8 or bb <= 1e-8:
        return -1e9
    return float((a * b).sum() / (aa * bb))


def _align_to_reference_skimage_polar(
    particle: np.ndarray,
    reference: np.ndarray,
    reference_polar: np.ndarray,
    particle_polar: np.ndarray | None = None,
) -> tuple[np.ndarray, float, float, tuple[float, float]]:
    """
    Polar MRA for one particle/reference pair:
    implicit angle search in polar coordinates -> translational phase correlation -> score.
    """
    if _warp_polar is None or _phase_xcorr_subpixel is None:
        raise RuntimeError("skimage-polar MRA requires scikit-image (warp_polar + phase_cross_correlation)")
    if particle_polar is None:
        particle_polar = _warp_polar(particle).astype(np.float32)
    shift, _err, _phase = _phase_xcorr_subpixel(reference_polar, particle_polar, normalization=None)
    # For our explicit polar layout, axis 0 is theta sampled over 360 bins.
    theta_bins = float(reference_polar.shape[0])
    angle = float(((-shift[0]) * (360.0 / max(theta_bins, 1.0))) % 360.0)
    rot = ndimage.rotate(particle, angle, reshape=False, order=1, mode="wrap")
    shifted, xy = _refine_translation_phasecorr(reference, rot)
    score = _cosine_score(shifted, reference)
    return shifted.astype(np.float32), float(angle), float(score), (float(xy[0]), float(xy[1]))


def _torch_rotate_batch(images: "torch.Tensor", angles_deg: "torch.Tensor") -> "torch.Tensor":
    """
    Rotate N images [N,H,W] by per-image angles using grid_sample.
    """
    n, h, w = int(images.shape[0]), int(images.shape[1]), int(images.shape[2])
    rad = angles_deg * (math.pi / 180.0)
    cos = torch.cos(rad)
    sin = torch.sin(rad)
    theta = torch.zeros((n, 2, 3), device=images.device, dtype=images.dtype)
    theta[:, 0, 0] = cos
    theta[:, 0, 1] = -sin
    theta[:, 1, 0] = sin
    theta[:, 1, 1] = cos
    grid = torch.nn.functional.affine_grid(theta, size=(n, 1, h, w), align_corners=False)
    out = torch.nn.functional.grid_sample(
        images[:, None, :, :],
        grid,
        mode="bilinear",
        padding_mode="zeros",
        align_corners=False,
    )
    return out[:, 0, :, :]


def _torch_phase_corr_integer_batch(ref_batch: "torch.Tensor", img_batch: "torch.Tensor") -> tuple["torch.Tensor", "torch.Tensor"]:
    """
    Integer-pixel phase correlation for batches [N,H,W].
    Returns dy, dx tensors shape [N].
    """
    fa = torch.fft.fftn(ref_batch, dim=(-2, -1))
    fb = torch.fft.fftn(img_batch, dim=(-2, -1))
    cps = fa * torch.conj(fb)
    denom = torch.abs(cps)
    denom = torch.where(denom == 0, torch.ones_like(denom), denom)
    cps = cps / denom
    cc = torch.fft.ifftn(cps, dim=(-2, -1)).real
    n, h, w = int(cc.shape[0]), int(cc.shape[1]), int(cc.shape[2])
    flat_idx = torch.argmax(cc.reshape(n, -1), dim=1)
    iy = flat_idx // w
    ix = flat_idx % w
    dy = iy.to(torch.float32)
    dx = ix.to(torch.float32)
    dy = torch.where(dy > (h // 2), dy - float(h), dy)
    dx = torch.where(dx > (w // 2), dx - float(w), dx)
    return dy, dx


def _torch_roll_batch(images: "torch.Tensor", dy: "torch.Tensor", dx: "torch.Tensor") -> "torch.Tensor":
    """
    Apply integer circular shifts to batch [N,H,W] using per-image dy/dx.
    """
    out = []
    for i in range(int(images.shape[0])):
        out.append(torch.roll(images[i], shifts=(int(dy[i].item()), int(dx[i].item())), dims=(0, 1)))
    return torch.stack(out, dim=0)


def _align_particle_to_refs_skimage_polar_torch(
    particle: np.ndarray,
    particle_polar: np.ndarray,
    refs_t: "torch.Tensor",
    polar_refs_t: "torch.Tensor",
    polar_refs_fft_t: "torch.Tensor | None" = None,
) -> tuple[np.ndarray, float, int, float, tuple[float, float]]:
    """
    Torch-accelerated per-particle evaluation across all references.
    Returns best shifted image, angle, reference index, and score.
    """
    device = refs_t.device
    dtype = refs_t.dtype
    k = int(refs_t.shape[0])

    pp = torch.from_numpy(particle_polar).to(device=device, dtype=dtype)
    pp = pp.unsqueeze(0).expand(k, -1, -1)
    fa = polar_refs_fft_t if polar_refs_fft_t is not None else torch.fft.fftn(polar_refs_t, dim=(-2, -1))
    fb = torch.fft.fftn(pp, dim=(-2, -1))
    cps = fa * torch.conj(fb)
    denom = torch.abs(cps)
    denom = torch.where(denom == 0, torch.ones_like(denom), denom)
    cps = cps / denom
    cc = torch.fft.ifftn(cps, dim=(-2, -1)).real
    tdim = int(cc.shape[1])
    rdim = int(cc.shape[2])
    flat_idx = torch.argmax(cc.reshape(k, -1), dim=1)
    shift_theta = (flat_idx // rdim).to(torch.float32)
    shift_theta = torch.where(shift_theta > (tdim // 2), shift_theta - float(tdim), shift_theta)
    angles = torch.remainder(-shift_theta * (360.0 / float(max(tdim, 1))), 360.0)

    p = torch.from_numpy(particle).to(device=device, dtype=dtype)
    p_batch = p.unsqueeze(0).expand(k, -1, -1).contiguous()
    rot_batch = _torch_rotate_batch(p_batch, angles)

    dy, dx = _torch_phase_corr_integer_batch(refs_t, rot_batch)
    sh_batch = _torch_roll_batch(rot_batch, dy, dx)

    rf = refs_t.reshape(k, -1)
    sf = sh_batch.reshape(k, -1)
    num = (rf * sf).sum(dim=1)
    den = torch.linalg.norm(rf, dim=1) * torch.linalg.norm(sf, dim=1)
    den = torch.clamp(den, min=1e-8)
    scores = num / den
    best = int(torch.argmax(scores).item())

    best_img = sh_batch[best].detach().cpu().numpy().astype(np.float32)
    best_ang = float(angles[best].item())
    best_score = float(scores[best].item())
    best_shift = (float(dy[best].item()), float(dx[best].item()))
    return best_img, best_ang, best, best_score, best_shift


def _phase_corr_shift_integer(ref: np.ndarray, img: np.ndarray) -> Tuple[float, float]:
    """
    Integer-pixel phase correlation fallback.
    Returns shift (dy, dx) to apply to img.
    """
    fa = sp_fft.fftn(ref)
    fb = sp_fft.fftn(img)
    cps = fa * np.conjugate(fb)
    denom = np.abs(cps)
    denom[denom == 0] = 1.0
    cps /= denom
    cc = sp_fft.ifftn(cps).real
    idx = np.unravel_index(np.argmax(cc), cc.shape)
    shifts = []
    for i, n in enumerate(cc.shape):
        s = float(idx[i])
        if s > n // 2:
            s -= n
        shifts.append(s)
    return float(shifts[0]), float(shifts[1])


def _refine_translation_phasecorr(ref: np.ndarray, img: np.ndarray) -> Tuple[np.ndarray, Tuple[float, float]]:
    """
    Refine translation after rotation using phase correlation.
    Uses skimage subpixel if available; otherwise integer fallback.
    """
    if _phase_xcorr_subpixel is not None:
        shift, _error, _phase = _phase_xcorr_subpixel(ref, img, upsample_factor=10, normalization=None)
        dy, dx = float(shift[0]), float(shift[1])
    else:
        dy, dx = _phase_corr_shift_integer(ref, img)
    shifted = ndimage.shift(img, shift=(dy, dx), order=1, mode="wrap")
    return shifted.astype(np.float32), (dy, dx)


def align_stack_to_references(
    stack: np.ndarray,
    references: np.ndarray,
    verbose: bool = True,
    n_threads: int = 1,
    progress_every: int = 250,
    log_each_particle: bool = False,
    compute_backend: str = "cpu",
    aligned_out_path: str | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Align each particle against all provided references using skimage polar alignment.

    Flow per particle:
    1) Build one polar transform of the particle.
    2) Compare against every reference polar map to estimate rotation.
    3) Refine translation in Cartesian space by phase correlation.
    4) Pick the highest-scoring reference/alignment.
    """
    if stack.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    if references.ndim != 3:
        raise ValueError("references must be 3D [k, y, x]")
    if stack.shape[1:] != references.shape[1:]:
        raise ValueError("stack and references image size must match")
    if _warp_polar is None or _phase_xcorr_subpixel is None:
        raise RuntimeError("skimage-polar MRA requires scikit-image")
    mra_torch_device = _resolve_torch_device(compute_backend)
    use_torch_mra = mra_torch_device is not None and torch is not None
    # torch.fft complex path is not currently supported on MPS for this workload.
    if use_torch_mra and mra_torch_device == "mps":
        use_torch_mra = False

    n = int(stack.shape[0])
    k = int(references.shape[0])
    # Normalize references once up front so per-particle scores are comparable.
    refs = np.stack([_normalize_image(r) for r in references], axis=0).astype(np.float32)
    h, w = refs.shape[1], refs.shape[2]
    polar_radius = max(8, int(min(h, w) // 2))
    polar_shape = (360, polar_radius)
    polar_center = ((h - 1) / 2.0, (w - 1) / 2.0)
    # Precompute reference polar maps once; this avoids recomputing per particle.
    polar_refs = np.stack(
        [
            _warp_polar(
                r,
                center=polar_center,
                radius=polar_radius,
                output_shape=polar_shape,
                scaling="linear",
            ).astype(np.float32)
            for r in refs
        ],
        axis=0,
    )
    refs_t = None
    polar_refs_t = None
    polar_refs_fft_t = None
    if use_torch_mra:
        # Torch path computes all reference comparisons for a particle in one dense batch.
        refs_t = torch.from_numpy(refs).to(device=mra_torch_device, dtype=torch.float32)
        polar_refs_t = torch.from_numpy(polar_refs).to(device=mra_torch_device, dtype=torch.float32)
        polar_refs_fft_t = torch.fft.fftn(polar_refs_t, dim=(-2, -1))

    if aligned_out_path is None:
        aligned = np.zeros_like(stack, dtype=np.float32)
    else:
        # For large runs, write aligned particles straight to disk-backed memmap.
        aligned = np.memmap(
            aligned_out_path,
            dtype=np.float32,
            mode="w+",
            shape=tuple(int(x) for x in stack.shape),
        )
    rotations = np.zeros((n,), dtype=np.float32)
    ref_indices = np.zeros((n,), dtype=np.int32)
    ref_scores = np.zeros((n,), dtype=np.float32)
    shifts = np.zeros((n, 2), dtype=np.float32)

    if verbose:
        xcorr_method = "skimage_subpixel" if _phase_xcorr_subpixel is not None else "integer_fallback"
        print(
            f"[mra] aligning particles to class references "
            f"(particles={n}, refs={k}, threads={int(n_threads)}, method=skimage-polar)"
        )
        print(f"[mra] translation refinement via phase correlation: {xcorr_method}")
        if use_torch_mra:
            print(f"[mra] torch acceleration enabled for skimage-polar on device={mra_torch_device}")
        elif mra_torch_device == "mps":
            print("[mra] torch skimage-polar disabled on MPS (complex FFT unsupported); using CPU path")
        print(f"[mra] expected evaluations (particle x reference): {n * k}")

    t_align = time.time()

    def _align_one(i: int) -> tuple[int, np.ndarray, float, int, float, float, float]:
        particle = stack[i]
        particle_polar = _warp_polar(
            particle,
            center=polar_center,
            radius=polar_radius,
            output_shape=polar_shape,
            scaling="linear",
        ).astype(np.float32)
        best_img = particle
        best_ang = 0.0
        best_ref = 0
        best_score = -1e9
        if use_torch_mra:
            best_img, best_ang, best_ref, best_score, best_shift = _align_particle_to_refs_skimage_polar_torch(
                particle=particle,
                particle_polar=particle_polar,
                refs_t=refs_t,
                polar_refs_t=polar_refs_t,
                polar_refs_fft_t=polar_refs_fft_t,
            )
            return (
                i,
                best_img.astype(np.float32),
                float(best_ang),
                int(best_ref),
                float(best_score),
                float(best_shift[0]),
                float(best_shift[1]),
            )
        best_dy = 0.0
        best_dx = 0.0
        # CPU path: evaluate every reference and keep winner.
        for r in range(k):
            img, ang, score, sh = _align_to_reference_skimage_polar(
                particle=particle,
                reference=refs[r],
                reference_polar=polar_refs[r],
                particle_polar=particle_polar,
            )
            if score > best_score:
                best_img = img
                best_ang = ang
                best_ref = r
                best_score = score
                best_dy = float(sh[0])
                best_dx = float(sh[1])
        return i, best_img.astype(np.float32), float(best_ang), int(best_ref), float(best_score), best_dy, best_dx

    effective_threads = int(n_threads)
    if use_torch_mra and mra_torch_device in ("cuda", "mps"):
        # Keep GPU work serialized at Python level; each task already evaluates all refs in a dense batch.
        effective_threads = 1
    if effective_threads <= 1:
        for i in range(n):
            i0, img, ang, refi, score, dy, dx = _align_one(i)
            aligned[i0] = img
            rotations[i0] = ang
            ref_indices[i0] = refi
            ref_scores[i0] = score
            shifts[i0, 0] = dy
            shifts[i0, 1] = dx
            if verbose and log_each_particle:
                print(
                    f"[mra] particle={i0} best_ref={refi} "
                    f"score={score:.6f} angle_deg={ang:.2f}"
                )
            if verbose and ((i + 1) % max(1, int(progress_every)) == 0 or (i + 1) == n):
                elapsed = time.time() - t_align
                done = i + 1
                evals = done * k
                eval_rate = evals / max(elapsed, 1e-6)
                part_rate = done / max(elapsed, 1e-6)
                eta = (n - done) / max(part_rate, 1e-6)
                print(
                    f"[mra] progress {done}/{n} elapsed={elapsed:.1f}s "
                    f"eval_rate={eval_rate:.1f}/s avg_pair_ms={(1000.0/max(eval_rate,1e-6)):.3f} "
                    f"avg_particle_ms={(1000.0/max(part_rate,1e-6)):.2f} eta={eta:.1f}s"
                )
    else:
        with ThreadPoolExecutor(max_workers=effective_threads) as ex:
            futures = {ex.submit(_align_one, i): i for i in range(n)}
            done = 0
            for fut in as_completed(futures):
                i0, img, ang, refi, score, dy, dx = fut.result()
                aligned[i0] = img
                rotations[i0] = ang
                ref_indices[i0] = refi
                ref_scores[i0] = score
                shifts[i0, 0] = dy
                shifts[i0, 1] = dx
                done += 1
                if verbose and log_each_particle:
                    print(
                        f"[mra] particle={i0} best_ref={refi} "
                        f"score={score:.6f} angle_deg={ang:.2f}"
                    )
                if verbose and (done % max(1, int(progress_every)) == 0 or done == n):
                    elapsed = time.time() - t_align
                    evals = done * k
                    eval_rate = evals / max(elapsed, 1e-6)
                    part_rate = done / max(elapsed, 1e-6)
                    eta = (n - done) / max(part_rate, 1e-6)
                    print(
                        f"[mra] progress {done}/{n} elapsed={elapsed:.1f}s "
                        f"eval_rate={eval_rate:.1f}/s avg_pair_ms={(1000.0/max(eval_rate,1e-6)):.3f} "
                        f"avg_particle_ms={(1000.0/max(part_rate,1e-6)):.2f} eta={eta:.1f}s"
                    )

    if verbose:
        elapsed = time.time() - t_align
        total_evals = n * k
        eval_rate = total_evals / max(elapsed, 1e-6)
        part_rate = n / max(elapsed, 1e-6)
        print(
            f"[mra] completed in {elapsed:.1f}s "
            f"(total_evals={total_evals}, eval_rate={eval_rate:.1f}/s, particle_rate={part_rate:.2f}/s)"
        )
    return aligned, rotations, ref_indices, ref_scores, shifts


@dataclass
class CanParams:
    num_presentations: int
    primary_learn: float
    secondary_learn: float
    max_age: int
    num_classes: int
    error_decay: float = 0.995
    add_speed_factor: float = 1.0
    progress_every: int = 5000
    can_threads: int = 1
    compute_backend: str = "cpu"
    checkpoint_every: int = 0
    early_stop_assignment_delta: float | None = None
    early_stop_error_rel_improve: float | None = None
    early_stop_patience: int = 0
    early_stop_min_presentations: int = 0


def _resolve_torch_device(compute_backend: str) -> str | None:
    if torch is None:
        return None
    backend = str(compute_backend).strip().lower()
    if backend == "cpu":
        return None
    if backend == "torch-cpu":
        return "cpu"
    if backend == "torch-cuda":
        if torch.cuda.is_available():
            return "cuda"
        raise RuntimeError("compute_backend=torch-cuda requested but CUDA is unavailable")
    if backend == "torch-mps":
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        raise RuntimeError("compute_backend=torch-mps requested but MPS is unavailable")
    if backend == "torch-auto":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    raise ValueError("compute_backend must be one of: cpu, torch-auto, torch-cuda, torch-mps, torch-cpu")


def can_classify(
    stack: np.ndarray,
    params: CanParams,
    seed: int = 0,
    verbose: bool = True,
    init_node_vectors: np.ndarray | None = None,
) -> Dict[str, Any]:
    """
    Competitive graph-based clustering (CAN).

    Training is online: one randomly chosen particle presentation per step.
    After training, all particles are assigned to nearest node to form class averages.
    """
    rng = np.random.default_rng(seed)
    data = np.asarray(stack, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError("stack must be 3D [n, y, x]")
    n, h, w = data.shape
    flat = data.reshape(n, -1).astype(np.float32, copy=False)

    device = _resolve_torch_device(getattr(params, "compute_backend", "cpu"))
    use_torch = device is not None
    if verbose:
        backend_name = str(getattr(params, "compute_backend", "cpu"))
        if use_torch:
            print(f"[can] compute backend={backend_name} resolved_device={device}")
        else:
            print(f"[can] compute backend={backend_name} resolved_device=cpu(numpy)")

    num_presentations = int(params.num_presentations)
    num_classes = int(params.num_classes)
    max_age = int(params.max_age)
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2")

    if use_torch:
        flat_t = torch.from_numpy(flat).to(device=device, dtype=torch.float32)
    else:
        flat_t = None

    init_flat = None
    if init_node_vectors is not None:
        init_arr = np.asarray(init_node_vectors, dtype=np.float32)
        if init_arr.ndim != 3:
            raise ValueError("init_node_vectors must be 3D [k, y, x]")
        if init_arr.shape[1:] != (h, w):
            raise ValueError("init_node_vectors image size must match stack image size")
        init_flat = init_arr.reshape(init_arr.shape[0], -1).astype(np.float32, copy=False)
        finite_mask = np.isfinite(init_flat).all(axis=1)
        init_flat = init_flat[finite_mask]
        if init_flat.shape[0] > 0:
            norms = np.linalg.norm(init_flat, axis=1)
            keep = norms > 1e-8
            init_flat = init_flat[keep]
        if init_flat.shape[0] > 0 and init_flat.shape[0] > num_classes:
            init_flat = init_flat[:num_classes]
        if verbose:
            print(f"[can] warm-start init nodes requested={int(init_arr.shape[0])} usable={int(init_flat.shape[0])}")

    if init_flat is not None and init_flat.shape[0] >= 2:
        if use_torch:
            node_arr_t = torch.from_numpy(init_flat).to(device=device, dtype=torch.float32).contiguous()
        else:
            node_arr_t = None
        nodes = [init_flat[i].copy() for i in range(init_flat.shape[0])] if not use_torch else []
    else:
        if use_torch:
            node_arr_t = torch.stack([flat_t.mean(dim=0), flat_t.mean(dim=0)], dim=0)
        else:
            node_arr_t = None
        nodes = [flat.mean(axis=0).copy(), flat.mean(axis=0).copy()] if not use_torch else []

    n_init_nodes = int(node_arr_t.shape[0]) if use_torch else len(nodes)
    errors = [0.0 for _ in range(max(2, n_init_nodes))]
    if len(errors) != n_init_nodes:
        errors = errors[:n_init_nodes]
    # Keep age semantics aligned with original CAN C++ code:
    # new/reset edges start at age 1, and aged edges are pruned at >= max_age.
    edges: Dict[Tuple[int, int], int] = {}
    for i in range(max(1, n_init_nodes - 1)):
        if i + 1 < n_init_nodes:
            edges[(i, i + 1)] = 1
    if n_init_nodes == 2 and (0, 1) not in edges:
        edges[(0, 1)] = 1

    # Interval controlling how often new nodes are inserted during training.
    add_interval = max(1, int(num_presentations / max(2, num_classes) / max(1e-6, params.add_speed_factor)))

    prim0 = float(params.primary_learn)
    sec0 = float(params.secondary_learn)

    def neighbors(i: int) -> List[int]:
        out = []
        for (a, b), _age in edges.items():
            if a == i:
                out.append(b)
            elif b == i:
                out.append(a)
        return out

    def edge_key(a: int, b: int) -> Tuple[int, int]:
        return (a, b) if a < b else (b, a)

    can_threads = max(1, int(getattr(params, "can_threads", 1)))
    if verbose:
        print(f"[can] training threads={can_threads}")

    checkpoint_every = int(getattr(params, "checkpoint_every", 0))
    stop_assign_thr = getattr(params, "early_stop_assignment_delta", None)
    stop_err_thr = getattr(params, "early_stop_error_rel_improve", None)
    stop_patience = int(getattr(params, "early_stop_patience", 0))
    stop_min_steps = int(getattr(params, "early_stop_min_presentations", 0))
    do_early_stop = (
        checkpoint_every > 0
        and stop_patience > 0
        and (stop_assign_thr is not None or stop_err_thr is not None)
    )
    if do_early_stop and verbose:
        print(
            f"[can] early-stop enabled: checkpoint_every={checkpoint_every} "
            f"assign_delta_thr={stop_assign_thr} err_rel_thr={stop_err_thr} "
            f"patience={stop_patience} min_steps={stop_min_steps}"
        )

    def _chunk_ranges(total: int, n_chunks: int) -> List[Tuple[int, int]]:
        n_chunks = max(1, min(int(n_chunks), int(total)))
        if total <= 0:
            return []
        step = (total + n_chunks - 1) // n_chunks
        out = []
        for s in range(0, total, step):
            e = min(total, s + step)
            out.append((s, e))
        return out

    def _get_node_arr_np() -> np.ndarray:
        if use_torch:
            return node_arr_t.detach().cpu().numpy().astype(np.float32)
        return np.stack(nodes, axis=0).astype(np.float32)

    def _checkpoint_assign_and_error(node_arr_np: np.ndarray) -> tuple[np.ndarray, float]:
        assign_tmp = np.zeros((n,), dtype=np.int32)
        min_dist = np.zeros((n,), dtype=np.float32)
        chunk = 128
        for start in range(0, n, chunk):
            end = min(n, start + chunk)
            block = flat[start:end]
            d = ((block[:, None, :] - node_arr_np[None, :, :]) ** 2).sum(axis=2)
            a = np.argmin(d, axis=1).astype(np.int32)
            assign_tmp[start:end] = a
            min_dist[start:end] = d[np.arange(d.shape[0]), a]
        return assign_tmp, float(np.mean(min_dist))

    t_can = time.time()
    prev_assign_cp = None
    prev_err_cp = None
    stable_count = 0
    checkpoint_history: list[dict[str, Any]] = []
    steps_run = num_presentations
    early_stopped = False
    for t in range(num_presentations):
        n_nodes = int(node_arr_t.shape[0]) if use_torch else len(nodes)
        # Random presentation with replacement (classical online CAN behavior).
        idx = int(rng.integers(0, n))
        if use_torch:
            x_t = flat_t[idx]
            dists_t = ((node_arr_t - x_t) ** 2).sum(dim=1)
            s1 = int(torch.argmin(dists_t).item())
            dists2_t = dists_t.clone()
            dists2_t[s1] = float("inf")
            s2 = int(torch.argmin(dists2_t).item())
            dists_s1 = float(dists_t[s1].item())
        else:
            x = flat[idx]
            node_arr = np.stack(nodes, axis=0)
            if can_threads <= 1:
                dists = ((node_arr - x) ** 2).sum(axis=1)
            else:
                dists = np.empty((node_arr.shape[0],), dtype=np.float32)

                def _dist_chunk(start: int, end: int) -> tuple[int, np.ndarray]:
                    block = node_arr[start:end]
                    diff = block - x[None, :]
                    vals = np.einsum("ij,ij->i", diff, diff, optimize=True).astype(np.float32)
                    return start, vals

                with ThreadPoolExecutor(max_workers=can_threads) as ex:
                    futures = [
                        ex.submit(_dist_chunk, s, e)
                        for (s, e) in _chunk_ranges(node_arr.shape[0], can_threads)
                    ]
                    for fut in futures:
                        s, vals = fut.result()
                        dists[s : s + vals.shape[0]] = vals
            s1 = int(np.argmin(dists))
            dists2 = dists.copy()
            dists2[s1] = np.inf
            s2 = int(np.argmin(dists2))
            dists_s1 = float(dists[s1])

        # Age winner edges so stale topology can be pruned.
        for nb in neighbors(s1):
            k = edge_key(s1, nb)
            edges[k] += 1

        # Move winner and its graph neighbors toward the presented sample.
        # Learning rate decays linearly over training.
        frac = max(0.0, (num_presentations - t) / max(1.0, float(num_presentations)))
        prim = prim0 * frac
        sec = sec0 * frac
        nbs = neighbors(s1)
        if use_torch:
            node_arr_t[s1] = node_arr_t[s1] + prim * (x_t - node_arr_t[s1])
            if nbs:
                nb_idx = torch.tensor(nbs, device=device, dtype=torch.long)
                node_arr_t[nb_idx] = node_arr_t[nb_idx] + sec * (x_t.unsqueeze(0) - node_arr_t[nb_idx])
        else:
            nodes[s1] = nodes[s1] + prim * (x - nodes[s1])
            if can_threads <= 1:
                for nb in nbs:
                    nodes[nb] = nodes[nb] + sec * (x - nodes[nb])
            else:
                def _update_neighbors_chunk(chunk: Sequence[int]) -> list[tuple[int, np.ndarray]]:
                    updated: list[tuple[int, np.ndarray]] = []
                    for nb in chunk:
                        newv = nodes[nb] + sec * (x - nodes[nb])
                        updated.append((int(nb), newv.astype(np.float32)))
                    return updated

                nb_ranges = _chunk_ranges(len(nbs), can_threads)
                with ThreadPoolExecutor(max_workers=can_threads) as ex:
                    futures = [
                        ex.submit(_update_neighbors_chunk, nbs[s:e])
                        for (s, e) in nb_ranges
                    ]
                    for fut in futures:
                        for nb, vec in fut.result():
                            nodes[nb] = vec

        errors[s1] += dists_s1

        # Remove edges that have aged out.
        to_drop = [k for k, age in edges.items() if age >= max_age]
        for k in to_drop:
            del edges[k]

        # Connect winner and runner-up; this is the core topology update.
        edges[edge_key(s1, s2)] = 1

        # decay errors
        errors = [e * float(params.error_decay) for e in errors]

        # Grow graph by splitting high-error regions until target node count is reached.
        if n_nodes < num_classes and t > 0 and t % add_interval == 0:
            q = int(np.argmax(np.asarray(errors)))
            q_neighbors = neighbors(q)
            if not q_neighbors:
                # Match original C++ fallback: if highest-error node is isolated,
                # connect it to its closest node first, then proceed with insertion.
                if use_torch:
                    q_vec = node_arr_t[q]
                    diff = node_arr_t - q_vec.unsqueeze(0)
                    dist = (diff * diff).sum(dim=1)
                    dist[q] = float("inf")
                    best_j = int(torch.argmin(dist).item())
                else:
                    q_vec = nodes[q]
                    best_j = -1
                    best_dist = float("inf")
                    for j in range(len(nodes)):
                        if j == q:
                            continue
                        diff = nodes[j] - q_vec
                        dist = float(np.dot(diff, diff))
                        if dist < best_dist:
                            best_dist = dist
                            best_j = j
                if best_j < 0:
                    continue
                edges[edge_key(q, best_j)] = 1
                q_neighbors = [best_j]
            f = q_neighbors[int(np.argmax([errors[j] for j in q_neighbors]))]
            if use_torch:
                r_vec_t = 0.5 * (node_arr_t[q] + node_arr_t[f])
            else:
                r_vec = 0.5 * (nodes[q] + nodes[f])
            r = int(node_arr_t.shape[0]) if use_torch else len(nodes)
            if use_torch:
                node_arr_t = torch.cat([node_arr_t, r_vec_t.unsqueeze(0)], dim=0)
            else:
                nodes.append(r_vec.astype(np.float32))
            errors.append(0.5 * (errors[q] + errors[f]))
            errors[q] *= 0.5
            errors[f] *= 0.5
            kqf = edge_key(q, f)
            if kqf in edges:
                del edges[kqf]
            edges[edge_key(q, r)] = 1
            edges[edge_key(f, r)] = 1

        if verbose and (t == 0 or (t + 1) % max(1, int(params.progress_every)) == 0 or (t + 1) == num_presentations):
            mean_error = float(np.mean(np.asarray(errors, dtype=np.float32))) if errors else 0.0
            curr_nodes = int(node_arr_t.shape[0]) if use_torch else len(nodes)
            print(
                f"[can] step {t+1}/{num_presentations} "
                f"nodes={curr_nodes} edges={len(edges)} mean_error={mean_error:.3e}"
            )

        if do_early_stop and ((t + 1) % checkpoint_every == 0 or (t + 1) == num_presentations):
            node_arr_np_cp = _get_node_arr_np()
            assign_cp, err_cp = _checkpoint_assign_and_error(node_arr_np_cp)
            assign_delta = None
            err_rel = None
            if prev_assign_cp is not None:
                assign_delta = float(np.mean(assign_cp != prev_assign_cp))
            if prev_err_cp is not None and prev_err_cp > 1e-12:
                err_rel = float((prev_err_cp - err_cp) / prev_err_cp)
            checkpoint_history.append(
                {
                    "step": int(t + 1),
                    "mean_winner_dist": float(err_cp),
                    "assignment_delta": assign_delta,
                    "error_rel_improve": err_rel,
                }
            )
            if verbose:
                print(
                    f"[can] checkpoint step={t+1} mean_winner_dist={err_cp:.6e} "
                    f"assignment_delta={assign_delta} error_rel_improve={err_rel}"
                )
            cond_assign = True if stop_assign_thr is None or assign_delta is None else (assign_delta <= float(stop_assign_thr))
            cond_err = True if stop_err_thr is None or err_rel is None else (err_rel <= float(stop_err_thr))
            if cond_assign and cond_err and (t + 1) >= max(0, stop_min_steps):
                stable_count += 1
            else:
                stable_count = 0
            if stable_count >= stop_patience:
                steps_run = int(t + 1)
                early_stopped = True
                if verbose:
                    print(f"[can] early stop triggered at step {steps_run} after {stable_count} stable checkpoints")
                break
            prev_assign_cp = assign_cp
            prev_err_cp = float(err_cp)

    # Final full assignment pass over all particles.
    if use_torch:
        node_arr_t_final = node_arr_t
        node_arr = node_arr_t_final.detach().cpu().numpy()
    else:
        node_arr = np.stack(nodes, axis=0)
    if verbose:
        print(f"[can] post-training assignment/averaging threads={can_threads}")
    assign = np.zeros((n,), dtype=np.int32)

    if use_torch:
        k_nodes = int(node_arr_t_final.shape[0])
        chunk = 512
        node_sq = (node_arr_t_final * node_arr_t_final).sum(dim=1)  # [K]
        for start in range(0, n, chunk):
            end = min(n, start + chunk)
            block = flat_t[start:end]
            # Low-memory squared distance: ||x||^2 + ||c||^2 - 2 x·c
            block_sq = (block * block).sum(dim=1, keepdim=True)  # [B,1]
            dot = block @ node_arr_t_final.t()  # [B,K]
            d = block_sq + node_sq.unsqueeze(0) - 2.0 * dot
            a = torch.argmin(d, dim=1).to(torch.int64)
            assign[start:end] = a.detach().cpu().numpy().astype(np.int32)
        # Keep averaging/count accumulation on CPU for stability and lower GPU memory pressure.
        class_avgs = np.zeros((k_nodes, h, w), dtype=np.float32)
        class_counts = np.zeros((k_nodes,), dtype=np.int32)
        for i in range(n):
            c = int(assign[i])
            class_avgs[c] += data[i]
            class_counts[c] += 1
        for c in range(k_nodes):
            if class_counts[c] > 0:
                class_avgs[c] /= float(class_counts[c])
    else:
        def _assign_chunk(start: int, end: int) -> tuple[int, np.ndarray]:
            block = flat[start:end]
            d = ((block[:, None, :] - node_arr[None, :, :]) ** 2).sum(axis=2)
            return start, np.argmin(d, axis=1).astype(np.int32)

        if can_threads <= 1 or n < 256:
            _s, _a = _assign_chunk(0, n)
            assign[:] = _a
        else:
            chunk = max(128, (n + can_threads - 1) // can_threads)
            with ThreadPoolExecutor(max_workers=can_threads) as ex:
                futures = []
                for start in range(0, n, chunk):
                    end = min(n, start + chunk)
                    futures.append(ex.submit(_assign_chunk, start, end))
                for fut in futures:
                    start, a = fut.result()
                    assign[start : start + a.shape[0]] = a

        # class averages from assigned particles (optionally threaded, behavior-preserving)
        class_avgs = np.zeros((len(nodes), h, w), dtype=np.float32)
        class_counts = np.zeros((len(nodes),), dtype=np.int32)

        def _acc_chunk(start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
            local_avgs = np.zeros((len(nodes), h, w), dtype=np.float32)
            local_counts = np.zeros((len(nodes),), dtype=np.int32)
            for i in range(start, end):
                c = int(assign[i])
                local_avgs[c] += data[i]
                local_counts[c] += 1
            return local_avgs, local_counts

        if can_threads <= 1 or n < 256:
            a, c = _acc_chunk(0, n)
            class_avgs += a
            class_counts += c
        else:
            chunk = max(128, (n + can_threads - 1) // can_threads)
            with ThreadPoolExecutor(max_workers=can_threads) as ex:
                futures = []
                for start in range(0, n, chunk):
                    end = min(n, start + chunk)
                    futures.append(ex.submit(_acc_chunk, start, end))
                for fut in futures:
                    a, c = fut.result()
                    class_avgs += a
                    class_counts += c

        for c in range(len(nodes)):
            if class_counts[c] > 0:
                class_avgs[c] /= float(class_counts[c])

    if verbose:
        print(f"[can] completed in {time.time()-t_can:.1f}s (steps_run={steps_run})")

    return {
        "assignments": assign,
        "class_averages": class_avgs,
        "class_counts": class_counts,
        "node_vectors": node_arr.reshape(node_arr.shape[0], h, w).astype(np.float32),
        "can_steps_run": int(steps_run),
        "can_early_stopped": bool(early_stopped),
        "can_checkpoint_history": checkpoint_history,
    }


def run_align_and_can(
    preprocessed_stack: np.ndarray,
    apix: float,
    align_iters: int,
    can_params: CanParams,
    mask_diameter_angstrom: float | None = None,
    seed: int = 0,
    verbose: bool = True,
    n_threads: int = 1,
    align_progress_every: int = 250,
    mra_log_each_particle: bool = False,
    center_class_averages: bool = True,
    iteration_callback: Callable[[str, int, np.ndarray, np.ndarray], None] | None = None,
    include_aligned_stack: bool = False,
    work_dir: str | None = None,
    can_init_nodes: np.ndarray | None = None,
) -> Dict[str, Any]:
    """
    End-to-end topology loop for one run.

    Iteration structure:
      CAN on current particle set -> MRA to CAN references.
    MRA alignment is always solved against the base preprocessed stack to avoid
    accumulating interpolation artifacts across iterations.
    """
    t0 = time.time()
    pre = np.asarray(preprocessed_stack, dtype=np.float32)
    if pre.ndim != 3:
        raise ValueError("preprocessed_stack must be 3D [n, y, x]")
    effective_apix = float(apix)
    if verbose:
        print(f"[pipeline] using preprocessed stack: shape={tuple(pre.shape)} apix={effective_apix:.5f}")

    mask_diameter_px = None
    if mask_diameter_angstrom is not None:
        if float(mask_diameter_angstrom) <= 0:
            raise ValueError("mask_diameter_angstrom must be > 0")
        if float(effective_apix) <= 0:
            raise ValueError("apix must be > 0 when mask_diameter_angstrom is set")
        mask_diameter_px = (1.25 * float(mask_diameter_angstrom)) / float(effective_apix)
        if verbose:
            print(
                f"[pipeline] circular mask enabled: particle_diam_ang={float(mask_diameter_angstrom):.2f} "
                f"mask_diam_ang={1.25*float(mask_diameter_angstrom):.2f} "
                f"mask_diam_px={mask_diameter_px:.2f} effective_apix={effective_apix:.5f}"
            )

    if align_iters < 1:
        raise ValueError("align_iters must be >= 1 (each iteration is CAN->MRA)")

    iteration_history: list[dict[str, Any]] = []
    iteration_mra_rotations: list[np.ndarray] = []
    iteration_mra_shifts: list[np.ndarray] = []
    iteration_mra_assignments: list[np.ndarray] = []
    iteration_mra_scores: list[np.ndarray] = []
    total_iters = int(align_iters)
    # `curr_particles` is what CAN sees each iteration. It is updated with MRA outputs.
    curr_particles = pre
    # Keep latest transforms/assignments so downstream outputs can be generated once.
    last_aligned = pre
    last_rotations = np.zeros((pre.shape[0],), dtype=np.float32)
    last_shifts = np.zeros((pre.shape[0], 2), dtype=np.float32)
    last_ref_assign = np.zeros((pre.shape[0],), dtype=np.int32)
    last_ref_scores = np.full((pre.shape[0],), np.nan, dtype=np.float32)
    last_can_n_classes = int(can_params.num_classes)

    can_seed = int(seed)
    temp_dir = None
    curr_particles_tmp_path = None
    if work_dir is not None:
        # Optional on-disk aligned buffers to keep memory bounded on large stacks.
        temp_dir = os.path.join(str(work_dir), "_tmp_align")
        os.makedirs(temp_dir, exist_ok=True)
    if verbose:
        print(f"[pipeline] topology loop: total_iterations={total_iters} (each iteration: CAN -> MRA)")

    can_out = None
    can_warm_start_nodes = np.asarray(can_init_nodes, dtype=np.float32) if can_init_nodes is not None else None
    for iter_idx in range(1, total_iters + 1):
        if verbose:
            print(f"[pipeline] iter {iter_idx}/{total_iters}: CAN on current particles")
        if can_warm_start_nodes is not None and verbose:
            print(
                f"[pipeline] iter {iter_idx}/{total_iters}: CAN warm-start from previous MRA "
                f"(nodes={int(can_warm_start_nodes.shape[0])})"
            )
        can_out = can_classify(
            curr_particles,
            params=can_params,
            seed=can_seed + (iter_idx - 1),
            verbose=verbose,
            init_node_vectors=can_warm_start_nodes,
        )
        if center_class_averages:
            class_avgs = np.asarray(can_out["class_averages"], dtype=np.float32)
            if verbose:
                print(f"[pipeline] centering CAN class averages (iter{iter_idx})")
            centered, _rot_ref, (m, med, mx) = _center_stack_to_rotavg_phasecorr(class_avgs)
            can_out["class_averages"] = centered
            if verbose:
                print(
                    f"[pipeline] CAN class-average phase-xcorr shifts (iter{iter_idx}): "
                    f"mean={m:.3f}px median={med:.3f}px max={mx:.3f}px"
                )
        if mask_diameter_px is not None:
            can_out["class_averages"] = _apply_circular_mask_stack(
                np.asarray(can_out["class_averages"], dtype=np.float32),
                diameter_px=mask_diameter_px,
            )
        last_can_n_classes = int(np.asarray(can_out["class_averages"]).shape[0])

        if iteration_callback is not None:
            iteration_callback(
                "can",
                int(iter_idx),
                np.asarray(can_out["class_averages"], dtype=np.float32),
                np.asarray(can_out["class_counts"], dtype=np.int32),
            )

        refs_full = np.asarray(can_out["class_averages"], dtype=np.float32)
        refs = refs_full
        counts = np.asarray(can_out["class_counts"], dtype=np.int32)
        # Skip empty references for MRA work, then map winning indices back to full class ids.
        keep = counts > 0
        keep_idx = np.where(keep)[0].astype(np.int32)
        if keep.any():
            refs = refs[keep]
        if refs.shape[0] == 0:
            raise RuntimeError("No non-empty class averages available for MRA")
        if verbose:
            print(
                f"[pipeline] iter {iter_idx}/{total_iters}: MRA to {refs.shape[0]} references "
                f"(input=preprocessed stack)"
            )
        aligned_tmp_path = None
        if temp_dir is not None:
            aligned_tmp_path = os.path.join(temp_dir, f"iter{iter_idx:03d}_aligned.f32")
        aligned, rotations, ref_assign_raw, ref_scores, shifts = align_stack_to_references(
            pre,
            refs,
            verbose=verbose,
            n_threads=n_threads,
            progress_every=align_progress_every,
            log_each_particle=mra_log_each_particle,
            compute_backend=getattr(can_params, "compute_backend", "cpu"),
            aligned_out_path=aligned_tmp_path,
        )
        if keep_idx.size > 0:
            ref_assign = keep_idx[np.asarray(ref_assign_raw, dtype=np.int32)]
        else:
            ref_assign = np.asarray(ref_assign_raw, dtype=np.int32)
        mra_avgs, mra_counts = _stack_averages_by_assignment(aligned, ref_assign, last_can_n_classes)
        nz = np.where(np.asarray(mra_counts, dtype=np.int32) > 0)[0]
        if nz.size >= 2:
            # Prioritize non-empty references with more support for next CAN warm start.
            order = nz[np.argsort(np.asarray(mra_counts, dtype=np.int32)[nz])[::-1]]
            can_warm_start_nodes = np.asarray(mra_avgs[order], dtype=np.float32).copy()
        else:
            can_warm_start_nodes = None
        iteration_mra_rotations.append(np.asarray(rotations, dtype=np.float32).copy())
        iteration_mra_shifts.append(np.asarray(shifts, dtype=np.float32).copy())
        iteration_mra_assignments.append(np.asarray(ref_assign, dtype=np.int32).copy())
        iteration_mra_scores.append(np.asarray(ref_scores, dtype=np.float32).copy())
        if iteration_callback is not None:
            iteration_callback(
                "mra",
                int(iter_idx),
                np.asarray(mra_avgs, dtype=np.float32),
                np.asarray(mra_counts, dtype=np.int32),
            )

        last_aligned = aligned
        last_rotations = rotations
        last_shifts = shifts
        last_ref_assign = ref_assign
        last_ref_scores = ref_scores
        curr_particles = aligned
        prev_tmp_path = curr_particles_tmp_path
        curr_particles_tmp_path = aligned_tmp_path
        if prev_tmp_path is not None and prev_tmp_path != curr_particles_tmp_path:
            try:
                os.remove(prev_tmp_path)
            except OSError:
                pass

        iteration_history.append(
            {
                "iteration": int(iter_idx),
                "can_n_classes": int(can_out["class_averages"].shape[0]),
                "can_nonempty_classes": int(np.count_nonzero(np.asarray(can_out["class_counts"]) > 0)),
                "mra_n_classes": int(mra_avgs.shape[0]),
                "mra_nonempty_classes": int(np.count_nonzero(mra_counts > 0)),
            }
        )

    if include_aligned_stack:
        can_out["aligned_stack"] = last_aligned
    can_out["rotations"] = last_rotations.astype(np.float32)
    can_out["shifts"] = last_shifts.astype(np.float32)
    can_out["mra_reference_assignments"] = last_ref_assign.astype(np.int32)
    can_out["mra_reference_scores"] = last_ref_scores.astype(np.float32)
    f_avg, f_counts, f_h1, f_h2, f_half_counts = class_half_averages(
        last_aligned,
        last_ref_assign,
        n_classes=int(last_can_n_classes),
        n_threads=int(n_threads),
    )
    can_out["final_preprocessed_class_averages"] = f_avg.astype(np.float32)
    can_out["final_preprocessed_class_counts"] = f_counts.astype(np.int32)
    can_out["final_preprocessed_half1"] = f_h1.astype(np.float32)
    can_out["final_preprocessed_half2"] = f_h2.astype(np.float32)
    can_out["final_preprocessed_half_counts"] = f_half_counts.astype(np.int32)
    can_out["mra_method"] = "skimage-polar"
    can_out["iteration_history"] = iteration_history
    can_out["iteration_mra_rotations"] = iteration_mra_rotations
    can_out["iteration_mra_shifts"] = iteration_mra_shifts
    can_out["iteration_mra_assignments"] = iteration_mra_assignments
    can_out["iteration_mra_scores"] = iteration_mra_scores
    can_out["effective_apix"] = float(effective_apix)
    if curr_particles_tmp_path is not None:
        can_out["aligned_stack_tmp_path"] = curr_particles_tmp_path
    if curr_particles_tmp_path is not None and not include_aligned_stack:
        try:
            os.remove(curr_particles_tmp_path)
        except OSError:
            pass
    if verbose:
        print(f"[pipeline] total runtime {time.time()-t0:.1f}s")
    return can_out

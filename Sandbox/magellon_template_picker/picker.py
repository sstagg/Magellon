"""
Native Python template picker with FindEM-like normalized correlation.

Atomic API:
    inputs  -> image, templates, params
    outputs -> particles + evaluative maps
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy import ndimage


def pick_particles(
    image: np.ndarray,
    templates: Sequence[np.ndarray],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run template matching, thresholding, peak finding, and assignment.

    Parameters
    ----------
    image:
        2D micrograph array.
    templates:
        Sequence of 2D template arrays.
    params:
        Dictionary of picker settings.
        Required:
          - "diameter_angstrom"
          - "pixel_size_angstrom"
        Optional:
          - "bin" (default 1.0)
          - "threshold" (default 0.4)
          - "max_threshold" (default None)
          - "max_peaks" (default 500)
          - "overlap_multiplier" (default 1.5)
          - "max_blob_size_multiplier" (default 1.0)
          - "min_blob_roundness" (default 0.0)
          - "peak_position" in {"maximum", "center"} (default "maximum")
          - "border_pixels" (default radius_in_pixels + 1)
          - "angle_ranges": list[(start, end, step)] matching template count
            default: [(0.0, 360.0, 10.0)] * len(templates)

    Returns
    -------
    dict with:
      - "particles": merged list of particle dicts
      - "template_results": per-template intermediate results
      - "merged_score_map": max score across templates
      - "assigned_template_map": template index of winner at each pixel
    """
    img = np.asarray(image, dtype=np.float32)
    if img.ndim != 2:
        raise ValueError("image must be 2D")
    if len(templates) < 1:
        raise ValueError("templates must contain at least one template")

    diameter = float(params["diameter_angstrom"])
    pixel_size = float(params["pixel_size_angstrom"])
    bin_factor = float(params.get("bin", 1.0))
    threshold = float(params.get("threshold", 0.4))
    max_threshold = params.get("max_threshold")
    max_peaks = int(params.get("max_peaks", 500))
    overlap_multiplier = float(params.get("overlap_multiplier", 1.5))
    max_blob_size_multiplier = float(params.get("max_blob_size_multiplier", 1.0))
    min_blob_roundness = float(params.get("min_blob_roundness", 0.0))
    peak_position = str(params.get("peak_position", "maximum"))
    if peak_position not in ("maximum", "center"):
        raise ValueError("peak_position must be 'maximum' or 'center'")

    radius_pixels = diameter / pixel_size / 2.0 / bin_factor
    border_pixels = int(params.get("border_pixels", int(radius_pixels) + 1))

    angle_ranges = params.get("angle_ranges")
    if angle_ranges is None:
        angle_ranges = [(0.0, 360.0, 10.0)] * len(templates)
    if len(angle_ranges) != len(templates):
        raise ValueError("angle_ranges must have one (start,end,step) tuple per template")

    normalized_image = _normalize_image(img)
    template_results: List[Dict[str, Any]] = []
    all_particles: List[Dict[str, Any]] = []

    for template_index, template in enumerate(templates, start=1):
        tmpl = np.asarray(template, dtype=np.float32)
        if tmpl.ndim != 2:
            raise ValueError(f"template #{template_index} is not 2D")
        if tmpl.shape[0] > normalized_image.shape[0] or tmpl.shape[1] > normalized_image.shape[1]:
            raise ValueError(f"template #{template_index} is larger than image")

        start_angle, end_angle, step_angle = angle_ranges[template_index - 1]
        score_map, raw_map, angle_map, norm_map = _match_template(
            image=normalized_image,
            template=tmpl,
            radius_pixels=radius_pixels,
            border_pixels=border_pixels,
            start_angle=float(start_angle),
            end_angle=float(end_angle),
            step_angle=float(step_angle),
        )

        particles = _extract_particles_from_map(
            score_map=score_map,
            angle_map=angle_map,
            template_index=template_index,
            threshold=threshold,
            radius_pixels=radius_pixels,
            max_peaks=max_peaks,
            overlap_multiplier=overlap_multiplier,
            max_blob_size_multiplier=max_blob_size_multiplier,
            min_blob_roundness=min_blob_roundness,
            peak_position=peak_position,
        )

        particles = _remove_border_particles(
            particles=particles,
            diameter_pixels=radius_pixels * 2.0,
            image_width=normalized_image.shape[1],
            image_height=normalized_image.shape[0],
        )
        all_particles.extend(particles)

        template_results.append(
            {
                "template_index": template_index,
                "score_map": score_map,
                "raw_correlation_max_map": raw_map,
                "normalization_map": norm_map,
                "angle_map": angle_map,
                "threshold_mask": score_map >= threshold,
                "particles": particles,
            }
        )

    merged_particles = _merge_particles(
        particles=all_particles,
        radius_pixels=radius_pixels,
        overlap_multiplier=overlap_multiplier,
        max_peaks=max_peaks,
        max_threshold=max_threshold,
    )

    stacked = np.stack([result["score_map"] for result in template_results], axis=0)
    merged_score_map = np.max(stacked, axis=0)
    assigned_template_map = np.argmax(stacked, axis=0).astype(np.int16) + 1

    return {
        "particles": merged_particles,
        "template_results": template_results,
        "merged_score_map": merged_score_map.astype(np.float32),
        "assigned_template_map": assigned_template_map,
    }


def _normalize_image(image: np.ndarray) -> np.ndarray:
    min_value = float(image.min())
    max_value = float(image.max())
    if max_value <= min_value:
        return np.full_like(image, 1e-6, dtype=np.float32)
    return (5.0 * (image - min_value) / (max_value - min_value) + 1e-6).astype(np.float32)


def _match_template(
    image: np.ndarray,
    template: np.ndarray,
    radius_pixels: float,
    border_pixels: int,
    start_angle: float,
    end_angle: float,
    step_angle: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mask = _circular_mask(template.shape, radius_pixels)
    norm_map = _local_normalization_map(image=image, template_mask=mask)

    raw_max_map = np.full(image.shape, -1.2, dtype=np.float32)
    angle_map = np.zeros(image.shape, dtype=np.float32)

    angles = np.arange(start_angle, end_angle - 0.1, step_angle, dtype=np.float32)
    if angles.size == 0:
        angles = np.array([start_angle], dtype=np.float32)

    image_fft = np.fft.fft2(image)
    mask_count = int(mask.sum())
    if mask_count <= 0:
        raise ValueError("template mask is empty; check diameter/pixel size/template dimensions")

    for angle in angles:
        rotated = ndimage.rotate(template, float(angle), reshape=False, order=1, mode="wrap")
        normalized_template = _normalize_template(rotated, mask)
        correlation = _correlation_map(image_fft, normalized_template, mask_count)
        keep = correlation > raw_max_map
        raw_max_map[keep] = correlation[keep]
        angle_map[keep] = angle

    with np.errstate(divide="ignore", invalid="ignore"):
        score_map = np.where(norm_map > 0.0, raw_max_map / norm_map, 0.0)

    # FFT correlation origin conventions can yield maps rotated by 180 degrees
    # relative to image coordinates. Re-orient to image row/column coordinates.
    score_map = np.roll(np.flip(score_map, axis=(0, 1)), shift=1, axis=(0, 1))
    raw_max_map = np.roll(np.flip(raw_max_map, axis=(0, 1)), shift=1, axis=(0, 1))
    norm_map = np.roll(np.flip(norm_map, axis=(0, 1)), shift=1, axis=(0, 1))
    angle_map = np.roll(np.flip(angle_map, axis=(0, 1)), shift=1, axis=(0, 1))

    if border_pixels > 0:
        score_map[:border_pixels, :] = 0.0
        score_map[:, :border_pixels] = 0.0
        score_map[-border_pixels:, :] = 0.0
        score_map[:, -border_pixels:] = 0.0

    return (
        score_map.astype(np.float32),
        raw_max_map.astype(np.float32),
        angle_map.astype(np.float32),
        norm_map.astype(np.float32),
    )


def _circular_mask(shape: Tuple[int, int], radius_pixels: float) -> np.ndarray:
    height, width = shape
    center_y = int(height / 2.0)
    center_x = int(width / 2.0)
    yy, xx = np.ogrid[:height, :width]
    distance_squared = (yy - center_y) ** 2 + (xx - center_x) ** 2
    return (distance_squared <= radius_pixels ** 2).astype(np.float32)


def _normalize_template(template: np.ndarray, mask: np.ndarray) -> np.ndarray:
    masked = template * mask
    nmask = float(mask.sum())
    mean = masked.sum() / nmask
    sum_squares = np.square(masked).sum()
    variance = (nmask * sum_squares - masked.sum() ** 2) / (nmask * nmask)
    if variance > 1e-5:
        stddev = math.sqrt(float(variance))
        normalized = (masked - mean) / stddev
    else:
        normalized = masked - mean
    return (normalized * mask).astype(np.float32)


def _fft_pad_center(template: np.ndarray, output_shape: Tuple[int, int]) -> np.ndarray:
    out = np.zeros(output_shape, dtype=np.float32)
    h, w = template.shape
    out[:h, :w] = template
    out = np.roll(out, shift=(-int(h / 2.0), -int(w / 2.0)), axis=(0, 1))
    return out


def _correlation_map(image_fft: np.ndarray, template: np.ndarray, nmask: int) -> np.ndarray:
    template_padded = _fft_pad_center(template, image_fft.shape)
    template_fft = np.fft.fft2(template_padded)
    corr = np.fft.ifft2(template_fft * np.conjugate(image_fft)).real
    return (corr / float(nmask)).astype(np.float32)


def _local_normalization_map(image: np.ndarray, template_mask: np.ndarray) -> np.ndarray:
    nmask = float(template_mask.sum())
    image_fft = np.fft.fft2(image)
    image_sq_fft = np.fft.fft2(image * image)
    mask_fft = np.fft.fft2(_fft_pad_center(template_mask, image.shape))

    conv1 = np.fft.ifft2(image_fft * mask_fft).real
    conv2 = np.fft.ifft2(image_sq_fft * mask_fft).real
    v = ((nmask * conv2) - (conv1 * conv1)) / (nmask * nmask)
    out = np.zeros(v.shape, dtype=np.float32)
    positive = v > 0.0
    out[positive] = np.sqrt(v[positive]).astype(np.float32)
    return out


def _extract_particles_from_map(
    score_map: np.ndarray,
    angle_map: np.ndarray,
    template_index: int,
    threshold: float,
    radius_pixels: float,
    max_peaks: int,
    overlap_multiplier: float,
    max_blob_size_multiplier: float,
    min_blob_roundness: float,
    peak_position: str,
) -> List[Dict[str, Any]]:
    particle_area = 4.0 * math.pi * radius_pixels ** 2
    max_blob_size = int(round(max_blob_size_multiplier * particle_area)) + 1

    mask = score_map >= threshold
    coverage = float(mask.mean()) * 100.0
    if coverage > 25.0:
        return []

    labels, blob_count = ndimage.label(mask)
    particles: List[Dict[str, Any]] = []

    for label_index in range(1, blob_count + 1):
        component = labels == label_index
        size = int(component.sum())
        if size < 1 or size > max_blob_size:
            continue

        roundness = _blob_roundness(component)
        if roundness < min_blob_roundness:
            continue

        values = score_map[component]
        mean_value = float(values.mean())
        std_value = float(values.std())

        rows, cols = np.nonzero(component)
        if peak_position == "maximum":
            local_idx = int(np.argmax(values))
            ycoord = int(rows[local_idx])
            xcoord = int(cols[local_idx])
        else:
            center_y, center_x = ndimage.center_of_mass(component.astype(np.float32))
            ycoord = int(round(float(center_y)))
            xcoord = int(round(float(center_x)))

        particles.append(
            {
                "x": xcoord,
                "y": ycoord,
                "score": mean_value,
                "stddev": std_value,
                "area": size,
                "roundness": roundness,
                "template_index": template_index,
                "label": f"template_{template_index}",
                "angle": float(angle_map[ycoord, xcoord]),
            }
        )

    particles = _remove_overlapping_particles(
        particles=particles,
        cutoff_pixels=overlap_multiplier * radius_pixels,
    )
    particles.sort(key=lambda p: p["score"], reverse=True)
    return particles[:max_peaks]


def _blob_roundness(component: np.ndarray) -> float:
    area = float(component.sum())
    if area <= 0:
        return 0.0
    eroded = ndimage.binary_erosion(component)
    perimeter_pixels = float((component & ~eroded).sum())
    if perimeter_pixels <= 0:
        return 0.0
    return float(4.0 * math.pi * area / (perimeter_pixels ** 2))


def _particle_distance_squared(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return float((a["y"] - b["y"]) ** 2 + (a["x"] - b["x"]) ** 2)


def _remove_overlapping_particles(
    particles: List[Dict[str, Any]],
    cutoff_pixels: float,
) -> List[Dict[str, Any]]:
    if not particles:
        return particles
    particles = sorted(particles, key=lambda p: p["score"], reverse=True)
    kept: List[Dict[str, Any]] = []
    cutoff_sq = cutoff_pixels ** 2 + 1.0
    for candidate in particles:
        too_close = any(_particle_distance_squared(candidate, picked) < cutoff_sq for picked in kept)
        if not too_close:
            kept.append(candidate)
    return kept


def _remove_border_particles(
    particles: Iterable[Dict[str, Any]],
    diameter_pixels: float,
    image_width: int,
    image_height: int,
) -> List[Dict[str, Any]]:
    radius = diameter_pixels / 2.0
    min_xy = radius
    max_x = image_width - radius
    max_y = image_height - radius
    return [
        p
        for p in particles
        if p["x"] > min_xy and p["y"] > min_xy and p["x"] < max_x and p["y"] < max_y
    ]


def _merge_particles(
    particles: List[Dict[str, Any]],
    radius_pixels: float,
    overlap_multiplier: float,
    max_peaks: int,
    max_threshold: float | None,
) -> List[Dict[str, Any]]:
    merged = _remove_overlapping_particles(
        particles=particles,
        cutoff_pixels=overlap_multiplier * radius_pixels,
    )
    if max_threshold is not None:
        merged = [p for p in merged if p["score"] < float(max_threshold)]
    merged.sort(key=lambda p: p["score"], reverse=True)
    return merged[:max_peaks]

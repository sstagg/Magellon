"""Ptolemy compute functions — the only place algorithm logic lives.

Wraps the vendored ptolemy pipeline so ``plugin.py`` can stay thin. Returns
plain dicts that ``plugin.py`` validates against the SDK output schemas.

The models load on first use and cache for the process lifetime — three
``ort.InferenceSession`` objects total.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
from scipy.ndimage import zoom as _zoom

from plugin.ptolemy.images import load_mrc, Exposure
from plugin.ptolemy import algorithms
from plugin.ptolemy.models import Wrapper as OnnxWrapper

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEIGHTS = os.path.join(_HERE, "weights")

LOWMAG_ONNX  = os.path.join(_WEIGHTS, "lowmag.onnx")
UNET_ONNX    = os.path.join(_WEIGHTS, "unet.onnx")
AVGPOOL_ONNX = os.path.join(_WEIGHTS, "avgpool.onnx")

# UNet_Segmenter pads/handles images up to this size; anything larger raises InputError.
_UNET_MAX_DIM = 2048


# --- lazy classifier / segmenter cache ---------------------------------------
# One InferenceSession per model, built once per process. ORT sessions are
# thread-safe (the C++ runtime serialises internally), so two PluginBrokerRunner
# threads sharing a cached Wrapper is fine.

_CACHE: Dict[str, OnnxWrapper] = {}


def _wrapper_for(path: str) -> OnnxWrapper:
    w = _CACHE.get(path)
    if w is None:
        w = OnnxWrapper(path)
        _CACHE[path] = w
    return w


# --- load the MRC into an ndarray -------------------------------------------

def _load(input_file: str) -> np.ndarray:
    ext = os.path.splitext(input_file)[1].lower()
    if ext in (".mrc", ".mrcs"):
        return load_mrc(input_file)
    # JPG/PNG/TIFF support via PIL — useful for evaluation on pre-rendered
    # rasters. Not the primary path; MRC is what Magellon imports.
    from PIL import Image
    return np.asarray(Image.open(input_file).convert("L")).astype(np.float32)


# --- square detection (low-mag) ---------------------------------------------

def run_square_detection(input_file: str) -> tuple[list[dict], list[int], float, None]:
    """Returns (detections, [height, width], grid_angle_deg, grid_pitch) in MRC pixel coordinates.
    grid_pitch is None for squares (the concept doesn't apply at low-mag)."""
    image = _load(input_file)
    img_h = int(image.shape[-2])
    img_w = int(image.shape[-1])

    ex = Exposure(image)
    ex.make_mask(algorithms.PMM_Segmenter())
    ex.process_mask(algorithms.LowMag_Process_Mask())
    ex.get_crops(algorithms.LowMag_Process_Crops())
    ex.score_crops(_wrapper_for(LOWMAG_ONNX), final=False)

    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    intens   = ex.mean_intensities
    scores   = ex.crops.scores

    dets = [
        {
            "vertices":   vertices[i],
            "center":     centers[i],
            "area":       float(areas[i]),
            "brightness": float(intens[i]),
            "score":      float(scores[i]),
        }
        for i in np.argsort(scores)[::-1]
    ]
    grid_angle = round(float(ex.rot_ang_deg), 2)
    return dets, [img_h, img_w], grid_angle, None


# --- hole detection helpers --------------------------------------------------

def _run_hole_core(image: np.ndarray) -> tuple[list[dict], float, float | None]:
    """Run the full Ptolemy hole-detection pipeline on ``image``.

    Returns (detections_sorted_by_score_desc, grid_angle_deg, grid_pitch_px).
    Detections use as_matrix_y() convention: center/vertices are [col, row].
    Raises on failure (BadMedMagError, InputError, etc.) so callers can retry.
    """
    ex = Exposure(image)

    seg = algorithms.UNet_Segmenter(64, 9, model_path=UNET_ONNX)
    seg.model = _wrapper_for(UNET_ONNX)
    ex.make_mask(seg)

    mask_proc = algorithms.MedMag_Process_Mask()
    ex.process_mask(mask_proc)
    ex.get_crops(algorithms.MedMag_Process_Crops())
    ex.score_crops(_wrapper_for(AVGPOOL_ONNX), final=False)

    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    scores   = ex.crops.scores

    dets = [
        {
            "vertices": vertices[i],
            "center":   centers[i],
            "area":     float(areas[i]),
            "score":    float(scores[i]),
        }
        for i in np.argsort(scores)[::-1]
    ]
    grid_angle = round(float(ex.rot_ang_deg), 2)
    grid_pitch = round(float(mask_proc.grid_pitch), 1) if hasattr(mask_proc, "grid_pitch") else None
    return dets, grid_angle, grid_pitch


def _dets_sane(dets: list[dict], img_h: int, img_w: int) -> bool:
    """Return True if the top detections look like individual holes.

    A result is considered insane when any of the top-5 detections covers more
    than 25 % of the image area — that means the UNet found large blobs instead
    of individual holes (scale mismatch).
    """
    if not dets:
        return False
    max_area = 0.25 * img_h * img_w
    return all(d["area"] < max_area for d in dets[:5])


def _offset_dets(
    dets: list[dict],
    scale: float,
    col_offset: int,
    row_offset: int,
) -> list[dict]:
    """Convert detections from upscaled-tile space to full-image space.

    Ptolemy's as_matrix_y() convention: center = [col, row], vertices = [[col, row], ...].
    Tile was extracted as image[row_offset:..., col_offset:...] then upscaled by ``scale``.
    """
    result = []
    for d in dets:
        verts = [[v[0] / scale + col_offset, v[1] / scale + row_offset]
                 for v in d["vertices"]]
        center = [d["center"][0] / scale + col_offset,
                  d["center"][1] / scale + row_offset]
        result.append({
            "vertices": verts,
            "center":   center,
            "area":     d["area"] / (scale * scale),
            "score":    d["score"],
        })
    return result


def _deduplicate(dets: list[dict], min_dist: float) -> list[dict]:
    """Remove detections whose centers are within min_dist of a higher-scored one."""
    kept: list[dict] = []
    for det in dets:  # already sorted score-desc
        cx, cy = det["center"]
        if not any(
            abs(cx - k["center"][0]) < min_dist and abs(cy - k["center"][1]) < min_dist
            for k in kept
        ):
            kept.append(det)
    return kept


def _tiled_hole_detection(
    image: np.ndarray,
    grid: int = 2,
) -> tuple[list[dict], float, float | None]:
    """Split image into grid×grid tiles, upscale each to _UNET_MAX_DIM, run
    hole detection on each, then stitch results back into full image coordinates.

    Used as fallback when native-scale detection produces implausibly large blobs.
    Each tile is upscaled so that small holes appear at the apparent size the
    UNet was trained on.
    """
    img_h, img_w = int(image.shape[-2]), int(image.shape[-1])
    tile_h = img_h // grid
    tile_w = img_w // grid

    all_dets: list[dict] = []
    all_angles: list[float] = []
    all_pitches: list[float] = []

    scale_h = _UNET_MAX_DIM / tile_h
    scale_w = _UNET_MAX_DIM / tile_w

    for r in range(grid):
        for c in range(grid):
            r0 = r * tile_h
            c0 = c * tile_w
            tile = image[r0:r0 + tile_h, c0:c0 + tile_w]

            # Upscale tile so small holes appear at the scale UNet was trained on
            upscaled = _zoom(tile, (scale_h, scale_w))

            try:
                tile_dets, angle, pitch = _run_hole_core(upscaled)
                all_angles.append(angle)
                # pitch is in upscaled-tile pixels; convert to full-image pixels
                if pitch is not None:
                    all_pitches.append(pitch / scale_h)

                # Use the mean of scale_h/scale_w for coordinate inversion
                mean_scale = (scale_h + scale_w) / 2
                all_dets.extend(_offset_dets(tile_dets, mean_scale, c0, r0))
            except Exception:
                pass  # tile may have too few holes or other failure — skip

    if not all_dets:
        return [], 0.0, None

    all_dets.sort(key=lambda d: d["score"], reverse=True)

    # Deduplicate holes detected near tile boundaries (within 10% of tile width)
    all_dets = _deduplicate(all_dets, min_dist=tile_w * 0.10)

    grid_angle = round(float(np.mean(all_angles)), 2) if all_angles else 0.0
    grid_pitch = round(float(np.mean(all_pitches)), 1) if all_pitches else None
    return all_dets, grid_angle, grid_pitch


# --- hole detection (med-mag / sq-level) ------------------------------------

def run_hole_detection(input_file: str) -> tuple[list[dict], list[int], float, float | None]:
    """Returns (detections, [height, width], grid_angle_deg, grid_pitch_px).

    Tries native scale first. If the image is larger than the UNet's maximum
    input dimension, or if the results look like large blobs (scale mismatch —
    holes too small for the UNet at this pixel size), automatically falls back
    to tiled detection: the image is split into 2×2 quadrants, each upscaled to
    _UNET_MAX_DIM so individual holes appear at the scale the UNet was trained on.
    """
    image = _load(input_file)
    img_h = int(image.shape[-2])
    img_w = int(image.shape[-1])

    # --- attempt 1: native scale (clamped to UNet max if image is large) ---
    max_dim = max(img_h, img_w)
    native_scale = min(1.0, _UNET_MAX_DIM / max_dim)
    try:
        if native_scale < 1.0:
            working = _zoom(image, native_scale)
        else:
            working = image

        dets, angle, pitch = _run_hole_core(working)

        scaled_h = int(img_h * native_scale)
        scaled_w = int(img_w * native_scale)
        if _dets_sane(dets, scaled_h, scaled_w):
            full_dets = _offset_dets(dets, native_scale, 0, 0) if native_scale < 1.0 else dets
            full_pitch = round(pitch / native_scale, 1) if (pitch and native_scale < 1.0) else pitch
            return full_dets, [img_h, img_w], angle, full_pitch
    except Exception:
        pass

    # --- attempt 2: tiled detection (handles small holes / dense grids) ---
    dets, angle, pitch = _tiled_hole_detection(image, grid=2)
    return dets, [img_h, img_w], angle, pitch

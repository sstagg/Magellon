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

from plugin.ptolemy.images import load_mrc, Exposure
from plugin.ptolemy import algorithms
from plugin.ptolemy.models import Wrapper as OnnxWrapper

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEIGHTS = os.path.join(_HERE, "weights")

LOWMAG_ONNX  = os.path.join(_WEIGHTS, "lowmag.onnx")
UNET_ONNX    = os.path.join(_WEIGHTS, "unet.onnx")
AVGPOOL_ONNX = os.path.join(_WEIGHTS, "avgpool.onnx")


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


# --- hole detection (med-mag) ------------------------------------------------

def run_hole_detection(input_file: str) -> tuple[list[dict], list[int], float, float]:
    """Returns (detections, [height, width], grid_angle_deg, grid_pitch_px) in MRC pixel coordinates.
    grid_pitch is the center-to-center hole spacing used by the lattice fitter."""
    image = _load(input_file)
    img_h = int(image.shape[-2])
    img_w = int(image.shape[-1])

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
    return dets, [img_h, img_w], grid_angle, grid_pitch

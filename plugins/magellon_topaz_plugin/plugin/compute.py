"""Topaz compute layer — onnxruntime-only, no torch.

Two operations:

* :func:`run_pick` — preprocess MRC + run detector ONNX + NMS + upscale
  coords. Mirrors ``topaz preprocess`` + ``topaz extract`` end-to-end.
* :func:`run_denoise` — patch-stitch through the denoise UNet ONNX,
  write the cleaned MRC to disk.

The three .onnx files load lazily and cache for the process lifetime.
ORT sessions are thread-safe so two PluginBrokerRunners sharing one
cached session is fine.

onnxruntime / mrcfile / topaz_lib imports are lazy (deferred to first
call) so unit tests that mock ``run_pick`` / ``run_denoise`` don't
have to install the heavyweight runtime. Production startup pays the
import cost on the first task — same total cost, just relocated.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import numpy as np


_HERE = os.path.dirname(os.path.abspath(__file__))
_WEIGHTS = os.path.join(_HERE, "weights")

DETECTOR_FILES = {
    "resnet16": "topaz_resnet16_u64.onnx",
    "resnet16_u64": "topaz_resnet16_u64.onnx",
    "resnet8":  "topaz_resnet8_u64.onnx",
    "resnet8_u64": "topaz_resnet8_u64.onnx",
}
DENOISER_FILES = {
    "unet": "topaz_unet_l2.onnx",
    "unet_l2": "topaz_unet_l2.onnx",
}

# ``Any`` here keeps the type-hint without forcing onnxruntime to be
# importable at module load. The runtime type is
# onnxruntime.InferenceSession.
_SESSION_CACHE: Dict[str, Any] = {}


def _session(filename: str) -> Any:
    import onnxruntime as ort  # lazy

    path = os.path.join(_WEIGHTS, filename)
    sess = _SESSION_CACHE.get(path)
    if sess is None:
        sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        _SESSION_CACHE[path] = sess
    return sess


def _load_mrc(path: str) -> np.ndarray:
    import mrcfile  # lazy

    with mrcfile.open(path, permissive=True) as m:
        arr = np.asarray(m.data)
        if arr.ndim == 3:
            arr = arr.reshape(arr.shape[-2], arr.shape[-1])
        return arr.astype(np.float32, copy=True)


# ---------------------------------------------------------------------------
# Particle picking
# ---------------------------------------------------------------------------

def run_pick(input_file: str, *, model: str = "resnet16",
             radius: int = 14, threshold: float = -3.0,
             scale: int = 8) -> List[dict]:
    """Pick particles. Coordinates returned in ORIGINAL image space."""
    from plugin.topaz_lib.nms import non_maximum_suppression  # lazy
    from plugin.topaz_lib.preprocess import preprocess  # lazy

    onnx_name = DETECTOR_FILES.get(model)
    if onnx_name is None:
        raise ValueError(f"Unknown detector '{model}'. "
                         f"Choices: {sorted(DETECTOR_FILES.keys())}")

    image = _load_mrc(input_file)
    pre, _meta = preprocess(image, scale=scale)

    sess = _session(onnx_name)
    in_name = sess.get_inputs()[0].name
    score_map = sess.run(None, {in_name: pre[np.newaxis, np.newaxis]})[0][0, 0]

    scores, coords = non_maximum_suppression(score_map, r=radius, threshold=threshold)
    coords_full = (coords * scale).astype(int)

    order = np.argsort(scores)[::-1]
    return [
        {
            "center": [int(coords_full[i, 0]), int(coords_full[i, 1])],
            "radius": int(radius * scale),
            "score":  float(scores[i]),
        }
        for i in order
    ]


# ---------------------------------------------------------------------------
# Denoising
# ---------------------------------------------------------------------------

def run_denoise(input_file: str, output_file: str, *,
                model: str = "unet", patch_size: int = 1024,
                padding: int = 128) -> dict:
    """Denoise an MRC and write the cleaned copy to ``output_file``.

    Returns a stats summary keyed on (input, output, model, shape, min,
    max, mean, std) — same shape the sandbox's denoise_algorithm.py
    emits, so the JSON contract is stable across paths.
    """
    import mrcfile  # lazy
    from plugin.topaz_lib.denoise_io import denoise_in_patches  # lazy

    onnx_name = DENOISER_FILES.get(model)
    if onnx_name is None:
        raise ValueError(f"Unknown denoiser '{model}'. "
                         f"Choices: {sorted(DENOISER_FILES.keys())}")

    image = _load_mrc(input_file)
    sess = _session(onnx_name)
    in_name = sess.get_inputs()[0].name

    def run_model(tile: np.ndarray) -> np.ndarray:
        out = sess.run(None, {in_name: tile[np.newaxis, np.newaxis]})[0]
        return out[0, 0]

    denoised = denoise_in_patches(image, run_model, patch_size=patch_size, padding=padding)

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with mrcfile.new(output_file, overwrite=True) as m:
        m.set_data(denoised.astype(np.float32))

    return {
        "input":  os.path.abspath(input_file),
        "output": os.path.abspath(output_file),
        "model":  model,
        "shape":  list(denoised.shape),
        "min":    float(np.min(denoised)),
        "max":    float(np.max(denoised)),
        "mean":   float(np.mean(denoised)),
        "std":    float(np.std(denoised)),
    }

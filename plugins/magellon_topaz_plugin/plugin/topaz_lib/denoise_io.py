"""Patch-and-stitch driver for the topaz denoiser — pure numpy.

Mirrors ``topaz.denoise.Denoise.denoise_patches``. The denoise UNet has
fully-convolutional inference, so an arbitrarily-sized image works in
principle, but full-image inference on a 7000x7000 micrograph blows up
the activation memory. Patch + stitch keeps memory bounded; the
``padding`` overlap absorbs the UNet's edge artifacts.
"""
from __future__ import annotations

from typing import Callable

import numpy as np


def denoise_in_patches(image: np.ndarray, run_model: Callable[[np.ndarray], np.ndarray],
                       patch_size: int = 1024, padding: int = 128) -> np.ndarray:
    """Denoise ``image`` (2D ndarray) by tiling.

    ``run_model(arr_2d) -> arr_2d`` is the inference closure — it
    receives a normalized patch (already ``(x - mean) / std``) and
    must return a same-sized denoised patch. The tile loop handles
    re-applying mean/std and stitching.
    """
    h, w = image.shape
    out = np.zeros_like(image, dtype=np.float32)

    for i in range(0, h, patch_size):
        for j in range(0, w, patch_size):
            si = max(0, i - padding)
            ei = min(h, i + patch_size + padding)
            sj = max(0, j - padding)
            ej = min(w, j + patch_size + padding)

            tile = image[si:ei, sj:ej]
            mu = float(tile.mean())
            std = float(tile.std())
            tile_n = (tile - mu) / std

            denoised_n = run_model(tile_n.astype(np.float32))
            denoised = denoised_n * std + mu

            inner_si = i - si
            inner_sj = j - sj
            out[i:i + patch_size, j:j + patch_size] = denoised[
                inner_si:inner_si + patch_size,
                inner_sj:inner_sj + patch_size,
            ]
    return out


def denoise_whole(image: np.ndarray, run_model: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
    """Single-shot denoise. Cheap on small images, OOMs on large ones —
    use ``denoise_in_patches`` for anything bigger than ~2k square."""
    mu = float(image.mean())
    std = float(image.std())
    norm = ((image - mu) / std).astype(np.float32)
    out = run_model(norm)
    return (out * std + mu).astype(np.float32)


__all__ = ["denoise_in_patches", "denoise_whole"]

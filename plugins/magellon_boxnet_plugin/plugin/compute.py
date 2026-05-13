"""BoxNet picker compute glue.

Reads an MRC, calls :func:`pick_with_boxnet`, writes ``particles.json``,
returns a small dict the plugin's result factory consumes.

Heavy imports (mrcfile, torch) are lazy so plugin contract tests run
without them; algorithm.py keeps the same convention.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _load_mrc(path: str) -> np.ndarray:
    """Read an .mrc as a 2D float32 array."""
    import mrcfile  # lazy

    with mrcfile.open(path, permissive=True) as m:
        arr = np.asarray(m.data, dtype=np.float32)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(
            f"micrograph at {path} has ndim={arr.ndim}, expected 2"
        )
    return arr


def _resolve_output_path(image_path: str, output_dir: Optional[str]) -> str:
    """``<output_dir or image_dir>/particles.json`` next to the image."""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, "particles.json")
    image_dir = os.path.dirname(os.path.abspath(image_path))
    return os.path.join(image_dir, "particles.json")


def run_boxnet_pick(
    *,
    image_path: str,
    threshold: float = 0.3,
    min_distance: int = 14,
    scale: int = 8,
    device: str = "auto",
    weights_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """End-to-end pick.

    Returns a dict with the output path + count for the plugin's result
    factory. ``particles`` is included in-process for callers that want
    to avoid re-reading the JSON; the bus path uses only the path
    (ratified rule 1: refs + summaries on the wire, not inline lists).
    """
    from plugin.algorithm import pick_with_boxnet  # lazy: pulls torch

    image = _load_mrc(image_path)

    picks = pick_with_boxnet(
        image,
        weights_path=weights_path,
        threshold=float(threshold),
        min_distance=int(min_distance),
        scale=int(scale),
        device=device,
    )

    out_path = _resolve_output_path(image_path, output_dir)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(picks, f, indent=2)

    return {
        "particles_json_path": out_path,
        "num_particles": len(picks),
        "particles": picks,
        "image_shape": list(image.shape),
    }

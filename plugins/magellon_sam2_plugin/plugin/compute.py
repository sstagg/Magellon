"""SAM2 inference — image loading, model caching, click-pick, and auto-pick.

Two modes
---------
click_pick
    Given (image_path, click_points) → segment the clicked region → return
    the mask centroid + convex-hull polygon + confidence score.

    The image embedding is cached by (image_path, mtime) with a 10-minute
    TTL so every successive click on the same micrograph reuses the encoder
    output (the expensive step, ~2-5 s on CPU; ~0.3 s on GPU).  The decoder
    pass is fast (<100 ms CPU / <10 ms GPU) on all model variants.

auto_pick
    SAM2AutomaticMaskGenerator sweeps the entire image with a point grid
    and returns every stable mask.  The filter chain keeps only candidates
    that match expected particle geometry (area range, circularity ≥ 0.3).
"""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model cache  (image_path, mtime, model_variant) → predictor-with-image-set
# ---------------------------------------------------------------------------

try:
    from cachetools import TTLCache
    _EMBED_CACHE: TTLCache = TTLCache(maxsize=4, ttl=600)
except ImportError:
    _EMBED_CACHE = {}  # type: ignore[assignment]

# Lazily built per-variant; keyed by model_variant str
_MODEL_CACHE: Dict[str, object] = {}


def _device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _build_sam2_model(model_variant: str):
    """Load (or return cached) SAM2 model.  Prefers from_pretrained (HF hub)
    which handles checkpoint download and config resolution automatically.
    Falls back to manual build with local weight download."""
    if model_variant in _MODEL_CACHE:
        return _MODEL_CACHE[model_variant]

    import torch
    device = _device()
    logger.info("Loading SAM2 model %s on %s …", model_variant, device)

    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        if hasattr(SAM2ImagePredictor, "from_pretrained"):
            model = SAM2ImagePredictor.from_pretrained(model_variant)
            _MODEL_CACHE[model_variant] = model
            logger.info("SAM2 predictor loaded via HuggingFace hub.")
            return model
    except Exception:
        logger.exception("from_pretrained failed; falling back to manual build")

    # Manual build: resolve config + download weights
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    weights_dir = Path(os.environ.get("SAM2_WEIGHTS_DIR", "/app/weights"))
    weights_dir.mkdir(parents=True, exist_ok=True)

    _CHECKPOINT_URLS = {
        "facebook/sam2.1-hiera-tiny":      "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt",
        "facebook/sam2.1-hiera-small":     "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        "facebook/sam2.1-hiera-base-plus": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt",
        "facebook/sam2.1-hiera-large":     "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
    }
    _CHECKPOINT_CONFIGS = {
        "facebook/sam2.1-hiera-tiny":      "configs/sam2.1/sam2.1_hiera_t.yaml",
        "facebook/sam2.1-hiera-small":     "configs/sam2.1/sam2.1_hiera_s.yaml",
        "facebook/sam2.1-hiera-base-plus": "configs/sam2.1/sam2.1_hiera_b+.yaml",
        "facebook/sam2.1-hiera-large":     "configs/sam2.1/sam2.1_hiera_l.yaml",
    }

    url = _CHECKPOINT_URLS.get(model_variant)
    cfg = _CHECKPOINT_CONFIGS.get(model_variant)
    if not url or not cfg:
        raise ValueError(f"Unknown SAM2 model variant: {model_variant!r}")

    slug = model_variant.split("/")[-1]
    ckpt = weights_dir / f"{slug}.pt"
    if not ckpt.exists():
        import urllib.request
        logger.info("Downloading %s → %s", url, ckpt)
        urllib.request.urlretrieve(url, ckpt)

    sam2_model = build_sam2(cfg, str(ckpt), device=device, apply_postprocessing=False)
    predictor = SAM2ImagePredictor(sam2_model)
    _MODEL_CACHE[model_variant] = predictor
    return predictor


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def _load_image_as_rgb(image_path: str) -> np.ndarray:
    """Read a cryo-EM micrograph (MRC or image file) and return uint8 RGB.

    MRC data is percentile-normalised [0,255] so SAM2 sees reasonable
    contrast regardless of the original data range.
    """
    path = Path(image_path)
    if path.suffix.lower() in {".mrc", ".mrcs"}:
        import mrcfile
        with mrcfile.open(str(path), permissive=True) as mrc:
            data = mrc.data.copy()
        if data.ndim == 3:
            data = data[0]  # first frame of a stack
        data = data.astype(np.float32)
        p2, p98 = np.percentile(data, (2, 98))
        span = max(float(p98 - p2), 1e-6)
        data = np.clip((data - p2) / span, 0.0, 1.0)
        gray = (data * 255).astype(np.uint8)
        return np.stack([gray, gray, gray], axis=-1)

    from PIL import Image
    img = Image.open(str(path)).convert("RGB")
    return np.asarray(img)


def _image_shape(image_path: str) -> Tuple[int, int]:
    """Return (height, width) without fully loading the image."""
    path = Path(image_path)
    if path.suffix.lower() in {".mrc", ".mrcs"}:
        import mrcfile
        with mrcfile.open(str(path), permissive=True) as mrc:
            ny, nx = int(mrc.header.ny), int(mrc.header.nx)
        return ny, nx
    from PIL import Image
    with Image.open(str(path)) as img:
        w, h = img.size
    return h, w


# ---------------------------------------------------------------------------
# Click-based interactive picking
# ---------------------------------------------------------------------------

def _cache_key(image_path: str, model_variant: str) -> tuple:
    path = Path(image_path)
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return (image_path, mtime, model_variant)


def _get_predictor_with_image(image_path: str, model_variant: str):
    """Return a SAM2ImagePredictor that already has the image embedded.

    The result is cached (TTL 10 min, max 4 images) so repeated clicks
    on the same micrograph skip the encoder pass.
    """
    key = _cache_key(image_path, model_variant)
    if key in _EMBED_CACHE:
        return _EMBED_CACHE[key]

    predictor = _build_sam2_model(model_variant)
    rgb = _load_image_as_rgb(image_path)
    predictor.set_image(rgb)
    _EMBED_CACHE[key] = predictor
    return predictor


def _convex_hull_polygon(mask: np.ndarray) -> List[List[float]]:
    """Return an ordered convex-hull polygon [[x,y],…] from a boolean mask."""
    ys, xs = np.where(mask)
    if len(xs) < 3:
        return []
    from scipy.spatial import ConvexHull, QhullError
    points = np.column_stack([xs, ys]).astype(float)
    try:
        hull = ConvexHull(points)
        return [[float(xs[i]), float(ys[i])] for i in hull.vertices]
    except QhullError:
        return []


def click_pick(
    image_path: str,
    click_points: List[dict],  # [{x, y, label}]
    model_variant: str = "facebook/sam2.1-hiera-tiny",
    mask_threshold: float = 0.5,
) -> dict:
    """Segment the region under the supplied prompt points.

    Returns a dict compatible with ``ClickPickResult``.
    """
    import torch

    predictor = _get_predictor_with_image(image_path, model_variant)

    coords = np.array([[p["x"], p["y"]] for p in click_points], dtype=np.float32)
    labels = np.array([int(p.get("label", 1)) for p in click_points], dtype=np.int32)

    with torch.no_grad():
        masks, scores, _ = predictor.predict(
            point_coords=coords,
            point_labels=labels,
            multimask_output=True,
        )

    # Pick the highest-scoring mask
    best = int(scores.argmax())
    mask = masks[best].astype(bool)
    confidence = float(scores[best])

    ys, xs = np.where(mask)
    h, w = mask.shape
    image_shape = [h, w]

    if len(xs) == 0:
        # SAM2 returned an empty mask — fall back to the click position
        cx, cy = float(click_points[0]["x"]), float(click_points[0]["y"])
        return {
            "centroid_x": cx,
            "centroid_y": cy,
            "mask_polygon": [],
            "confidence": 0.0,
            "radius_estimate": 15.0,
            "image_shape": image_shape,
        }

    cx = float(xs.mean())
    cy = float(ys.mean())
    radius = float(math.sqrt(len(xs) / math.pi))
    polygon = _convex_hull_polygon(mask)

    return {
        "centroid_x": cx,
        "centroid_y": cy,
        "mask_polygon": polygon,
        "confidence": confidence,
        "radius_estimate": radius,
        "image_shape": image_shape,
    }


# ---------------------------------------------------------------------------
# Full-image automatic picking
# ---------------------------------------------------------------------------

def _circularity(area: int, perimeter: float) -> float:
    if perimeter <= 0:
        return 0.0
    return 4.0 * math.pi * area / (perimeter ** 2)


def _mask_perimeter(mask: np.ndarray) -> float:
    """Fast perimeter estimate via boundary pixel count."""
    from scipy import ndimage
    eroded = ndimage.binary_erosion(mask)
    return float((mask & ~eroded).sum())


def auto_pick(
    image_path: str,
    model_variant: str = "facebook/sam2.1-hiera-tiny",
    stability_score_threshold: float = 0.85,
    predicted_iou_threshold: float = 0.75,
    image_pixel_size: float = 1.0,
    particle_diameter_min_angstrom: float = 100.0,
    particle_diameter_max_angstrom: float = 500.0,
    min_circularity: float = 0.3,
    output_dir: Optional[str] = None,
) -> dict:
    """Run SAM2AutomaticMaskGenerator and return particle picks.

    Returns a dict with keys: num_particles, particles_json_path, image_shape.
    """
    import json
    import torch

    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

    sam2_base = _build_sam2_model(model_variant)
    # from_pretrained returns a SAM2ImagePredictor; auto-mask needs the raw model
    raw_model = getattr(sam2_base, "model", sam2_base)

    rgb = _load_image_as_rgb(image_path)
    h, w = rgb.shape[:2]

    # Convert diameter bounds from Å to pixels, then to area bounds
    px_per_ang = 1.0 / max(image_pixel_size, 1e-6)
    r_min_px = (particle_diameter_min_angstrom / 2.0) * px_per_ang
    r_max_px = (particle_diameter_max_angstrom / 2.0) * px_per_ang
    area_min = max(1, int(math.pi * r_min_px ** 2))
    area_max = int(math.pi * r_max_px ** 2)

    generator = SAM2AutomaticMaskGenerator(
        raw_model,
        stability_score_thresh=stability_score_threshold,
        pred_iou_thresh=predicted_iou_threshold,
        min_mask_region_area=area_min,
    )

    with torch.no_grad():
        masks_data = generator.generate(rgb)

    particles = []
    for m in masks_data:
        area = int(m["area"])
        if area < area_min or area > area_max:
            continue
        seg: np.ndarray = m["segmentation"]
        perim = _mask_perimeter(seg)
        circ = _circularity(area, perim)
        if circ < min_circularity:
            continue
        ys, xs = np.where(seg)
        cx = float(xs.mean())
        cy = float(ys.mean())
        radius = float(math.sqrt(area / math.pi))
        particles.append({
            "x": cx,
            "y": cy,
            "score": float(m.get("predicted_iou", 0.0)),
            "radius": radius,
        })

    # Write JSON output
    stem = Path(image_path).stem
    out_dir = Path(output_dir) if output_dir else Path(image_path).parent / "sam2_picks" / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = str(out_dir / "picks.json")
    with open(json_path, "w") as f:
        json.dump(particles, f)

    return {
        "num_particles": len(particles),
        "particles_json_path": json_path,
        "image_shape": [h, w],
    }

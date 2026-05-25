"""
Particle picking demo — template matching + visualization.

Image : C:/magellon/gpfs/home/24dec03a/original/24dec03a_00034gr_00005sq_v01_00003hl_00018ex.mrc
        4096×4096, pixel_size = 0.79 Å/px

Templates : C:/magellon/gpfs/templates/origTemplate{1,2,3}.mrc
            448×448, pixel_size ≈ unset (treated as same as image)

Strategy:
  1. Downsample image and templates by 'bin_factor' to speed up correlation.
  2. Normalise cross-correlate each template against the downsampled image.
  3. Take the per-pixel max across all templates.
  4. Find local maxima (NMS) above threshold.
  5. Back-project picks to original pixel space.
  6. Visualise on an 8-bit greyscale JPEG with coloured circles + IDs.
  7. Also save picks as JSON.
"""

import json
import math
import os
import sys

import mrcfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import maximum_filter, zoom
from scipy.signal import fftconvolve
from skimage.feature import peak_local_max

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
IMAGE_MRC   = r"C:\magellon\gpfs\home\24dec03a\original\24dec03a_00034gr_00005sq_v01_00003hl_00018ex.mrc"
TEMPLATE_DIR = r"C:\magellon\gpfs\templates"
OUTPUT_DIR   = r"C:\projects\Magellon\CoreService\sandbox\particle_picking_demo\output"
IMAGE_NAME   = "24dec03a_00034gr_00005sq_v01_00003hl_00018ex"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
BIN_FACTOR   = 8          # downsample image and templates by this factor
THRESHOLD    = 0.20       # normalised cross-correlation score cutoff
MIN_DISTANCE = 14         # NMS: min distance between peak centres (in binned px)
PARTICLE_RADIUS_ORIG = 40  # radius drawn on original image, in original px

# ---------------------------------------------------------------------------
# Step 1 — Load and bin the micrograph
# ---------------------------------------------------------------------------
print(f"Loading micrograph: {IMAGE_MRC}")
with mrcfile.open(IMAGE_MRC, mode='r', permissive=True) as mrc:
    raw = mrc.data.astype(np.float32)

print(f"  Original shape: {raw.shape}")

# Downsample by averaging (zoom is cleaner than stride slicing)
binned = zoom(raw, 1.0 / BIN_FACTOR, order=1)
print(f"  Binned  shape : {binned.shape}  (bin={BIN_FACTOR})")

# Normalise the binned image (zero-mean, unit std) for NCC
def normalise(a: np.ndarray) -> np.ndarray:
    a = a - a.mean()
    std = a.std()
    if std > 0:
        a /= std
    return a

img_norm = normalise(binned)

# ---------------------------------------------------------------------------
# Step 2 — Load and bin the templates
# ---------------------------------------------------------------------------
template_paths = sorted(
    os.path.join(TEMPLATE_DIR, f) for f in os.listdir(TEMPLATE_DIR) if f.endswith(".mrc")
)
print(f"\nFound {len(template_paths)} templates:")
templates_binned = []
for tp in template_paths:
    with mrcfile.open(tp, mode='r', permissive=True) as mrc:
        t = mrc.data.astype(np.float32)
    print(f"  {os.path.basename(tp)}: {t.shape}")
    # Downsample template to match binned image pixel size
    tb = zoom(t, 1.0 / BIN_FACTOR, order=1)
    templates_binned.append(normalise(tb))

# ---------------------------------------------------------------------------
# Step 3 — Normalised cross-correlation for each template
# ---------------------------------------------------------------------------
print("\nRunning template matching...")
score_maps = []
for i, tmpl in enumerate(templates_binned):
    th, tw = tmpl.shape
    print(f"  Template {i+1}: binned size = {tmpl.shape}")

    # NCC: correlate image with template, then normalise by local image energy
    # Full NCC denominator: compute local std in a template-sized window.
    # Simple approximation: precompute correlation, divide by (template L2 norm).
    corr = fftconvolve(img_norm, tmpl[::-1, ::-1], mode='same')
    # Normalise by template norm so score is in [-1, 1]
    tmpl_norm_val = np.linalg.norm(tmpl)
    if tmpl_norm_val > 0:
        corr /= tmpl_norm_val
    score_maps.append(corr)

# Combined score: maximum across templates
combined = np.max(np.stack(score_maps, axis=0), axis=0)
print(f"  Combined score map: min={combined.min():.3f}  max={combined.max():.3f}  mean={combined.mean():.3f}")

# ---------------------------------------------------------------------------
# Step 4 — Peak detection (NMS)
# ---------------------------------------------------------------------------
print(f"\nDetecting peaks (threshold={THRESHOLD}, min_distance={MIN_DISTANCE} binned px)...")
peaks = peak_local_max(
    combined,
    min_distance=MIN_DISTANCE,
    threshold_abs=THRESHOLD,
    exclude_border=True,
)
print(f"  Found {len(peaks)} particles")

# Back-project to original pixel space
picks_orig = [(int(r * BIN_FACTOR), int(c * BIN_FACTOR)) for r, c in peaks]
scores     = [float(combined[r, c]) for r, c in peaks]

# Save JSON
picks_json = [
    {"x": c, "y": r, "score": s, "id": f"tp-{i}"}
    for i, ((r, c), s) in enumerate(zip(picks_orig, scores))
]
json_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_picks.json")
with open(json_path, "w") as f:
    json.dump(picks_json, f, indent=2)
print(f"  Picks JSON saved: {json_path}")

# ---------------------------------------------------------------------------
# Step 5 — Build visualisation on the full-resolution PNG
# ---------------------------------------------------------------------------
# Use the existing PNG thumbnail if available (much faster than rendering MRC)
thumb_png = r"C:\magellon\gpfs\home\24dec03a\images\24dec03a_00034gr_00005sq_v01_00003hl_00018ex.png"
if os.path.exists(thumb_png):
    print(f"\nLoading existing thumbnail: {thumb_png}")
    img_pil = Image.open(thumb_png).convert("RGB")
    # Scale particle positions to thumbnail resolution
    orig_h, orig_w = raw.shape
    th_w, th_h = img_pil.size
    sx = th_w / orig_w
    sy = th_h / orig_h
    def to_thumb(r_orig, c_orig):
        return int(c_orig * sx), int(r_orig * sy)
    radius_thumb = max(3, int(PARTICLE_RADIUS_ORIG * sx))
else:
    # Render from raw MRC data — clip to 8-bit for display
    print("\nRendering MRC as 8-bit image...")
    lo, hi = np.percentile(raw, [1, 99])
    vis = np.clip((raw - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    img_pil = Image.fromarray(vis).convert("RGB")
    def to_thumb(r_orig, c_orig):
        return c_orig, r_orig
    radius_thumb = PARTICLE_RADIUS_ORIG

# Draw circles around each pick
print("Drawing particle overlays...")
draw = ImageDraw.Draw(img_pil, "RGBA")

# Use a semi-transparent fill and bright outline
FILL   = (255, 80, 0, 50)   # orange, mostly transparent
OUTLINE = (255, 200, 0, 220)  # yellow, mostly opaque
LINE_W = max(1, radius_thumb // 8)

# Build a simple colormap: high-score = green, low = red
def score_color(s, s_min, s_max):
    t = (s - s_min) / max(s_max - s_min, 1e-6)
    r = int(255 * (1 - t))
    g = int(255 * t)
    return (r, g, 50, 220)

s_arr = np.array(scores)
s_min, s_max = s_arr.min(), s_arr.max()

for i, ((r, c), s) in enumerate(zip(picks_orig, scores)):
    cx, cy = to_thumb(r, c)
    col = score_color(s, s_min, s_max)
    draw.ellipse(
        [cx - radius_thumb, cy - radius_thumb, cx + radius_thumb, cy + radius_thumb],
        fill=FILL,
        outline=col,
        width=LINE_W,
    )
    # Small ID label
    if radius_thumb > 8:
        draw.text((cx + radius_thumb + 2, cy - 6), str(i), fill=(255, 255, 100, 255))

# Score-map overlay as a semi-transparent heat layer at thumbnail resolution
print("Adding correlation score-map overlay...")
sm_vis = combined - combined.min()
sm_vis /= sm_vis.max()
sm_resized = zoom(sm_vis, (img_pil.height / sm_vis.shape[0], img_pil.width / sm_vis.shape[1]), order=1)

# Map to orange-heat RGBA
heat_r = (sm_resized * 255).astype(np.uint8)
heat_g = (sm_resized * 120).astype(np.uint8)
heat_b = np.zeros_like(heat_r)
heat_a = (sm_resized * 80).astype(np.uint8)   # subtle overlay
heat_rgba = np.stack([heat_r, heat_g, heat_b, heat_a], axis=-1)
heat_img = Image.fromarray(heat_rgba, mode="RGBA")

base_rgba = img_pil.convert("RGBA")
composited = Image.alpha_composite(base_rgba, heat_img)
img_pil = composited.convert("RGB")

# Title banner
draw2 = ImageDraw.Draw(img_pil)
banner = (
    f"Template matching  |  {len(picks_orig)} particles  "
    f"|  threshold={THRESHOLD}  |  bin={BIN_FACTOR}  "
    f"|  min_dist={MIN_DISTANCE}px"
)
draw2.rectangle([0, 0, img_pil.width, 28], fill=(20, 20, 20))
draw2.text((8, 6), banner, fill=(255, 255, 200))

# Save result
out_img_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_template_picking.jpg")
img_pil.save(out_img_path, "JPEG", quality=90)
print(f"\nResult image saved: {out_img_path}")

# Also save score map as a separate image
sm_8bit = (sm_vis * 255).astype(np.uint8)
sm_full = zoom(sm_8bit, (img_pil.height / sm_8bit.shape[0], img_pil.width / sm_8bit.shape[1]), order=1)
sm_img = Image.fromarray(sm_full).convert("RGB")
sm_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_score_map.jpg")
sm_img.save(sm_path, "JPEG", quality=85)
print(f"Score map  saved : {sm_path}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "="*60)
print(f"  Particles detected : {len(picks_orig)}")
print(f"  Score range        : {s_min:.3f} – {s_max:.3f}")
print(f"  Threshold used     : {THRESHOLD}")
print(f"  NMS min_distance   : {MIN_DISTANCE} binned px ({MIN_DISTANCE * BIN_FACTOR} orig px)")
print(f"  Result image       : {out_img_path}")
print(f"  Picks JSON         : {json_path}")
print("="*60)

"""
Topaz particle picking demo.

Uses Topaz's pretrained ResNet8-u64 model (general-purpose, no training needed).
Pipeline:
  1. topaz downsample  — DFT-based 8x downsampling (0.79 Å/px → 6.32 Å/px)
  2. topaz normalize   — 2-component Gaussian normalisation (Topaz recommended)
  3. topaz extract     — ResNet8-u64 inference + NMS peak extraction
  4. Visualise picks on the original-resolution image with coloured circles.

Topaz reference: Bepler et al. (2019) Nature Methods  16, 1153-1160
                 https://github.com/tbepler/topaz
"""

import json
import os
import subprocess
import sys
import tempfile

import mrcfile
import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
IMAGE_MRC    = r"C:\magellon\gpfs\home\24dec03a\original\24dec03a_00034gr_00005sq_v01_00003hl_00018ex.mrc"
OUTPUT_DIR   = r"C:\projects\Magellon\CoreService\sandbox\particle_picking_demo\output"
IMAGE_NAME   = "24dec03a_00034gr_00005sq_v01_00003hl_00018ex"
TOPAZ_MODELS = r"C:\projects\Magellon\CoreService\venv\Lib\site-packages\topaz\pretrained\detector"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
DOWN_SCALE    = 8      # Topaz -s flag (8x DFT downsampling)
PARTICLE_RAD  = 14     # radius at downsampled resolution for NMS (px)
THRESHOLD     = -3     # Topaz log-likelihood threshold (-6 default = very sensitive)
MODEL         = os.path.join(TOPAZ_MODELS, "resnet8_u64.sav")

# ---------------------------------------------------------------------------
# Step 1 — Topaz downsample (DFT, band-limited — Topaz preferred approach)
# ---------------------------------------------------------------------------
ds_path  = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_topaz_ds{DOWN_SCALE}.mrc")
nor_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_topaz_norm.mrc")
coord_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_topaz_picks.txt")

print(f"[1/4] Downsampling with topaz downsample (scale={DOWN_SCALE})...")
result = subprocess.run(
    [sys.executable, "-m", "topaz.commands.downsample",
     "-s", str(DOWN_SCALE),
     "-o", ds_path,
     IMAGE_MRC],
    capture_output=True, text=True,
)
if result.returncode != 0:
    # Fallback: topaz downsample as CLI
    result = subprocess.run(
        ["topaz", "downsample", "-s", str(DOWN_SCALE), "-o", ds_path, IMAGE_MRC],
        capture_output=True, text=True,
    )
if result.returncode != 0:
    print("topaz downsample failed:", result.stderr)
    # Manual fallback: write a pre-downsampled MRC
    print("  Falling back to manual downsampling...")
    with mrcfile.open(IMAGE_MRC, mode='r', permissive=True) as mrc:
        raw = mrc.data.astype(np.float32)
    from scipy.ndimage import zoom
    ds_data = zoom(raw, 1.0 / DOWN_SCALE, order=1)
    with mrcfile.new(ds_path, overwrite=True) as mrc:
        mrc.set_data(ds_data)
    print(f"  Manual DS saved: {ds_path}")
else:
    print(f"  Downsampled MRC: {ds_path}")

# Verify
with mrcfile.open(ds_path, mode='r', permissive=True) as mrc:
    ds_data = mrc.data
    print(f"  Downsampled shape: {ds_data.shape}")

# ---------------------------------------------------------------------------
# Step 2 — Topaz normalize
# ---------------------------------------------------------------------------
print(f"\n[2/4] Normalising with topaz normalize...")
result = subprocess.run(
    ["topaz", "normalize", "-o", nor_path, ds_path],
    capture_output=True, text=True,
)
if result.returncode != 0:
    print("  topaz normalize failed:", result.stderr[:200])
    print("  Using raw downsampled image for extraction...")
    nor_path = ds_path
else:
    print(f"  Normalised MRC: {nor_path}")

# ---------------------------------------------------------------------------
# Step 3 — topaz extract with pretrained ResNet8-u64
# ---------------------------------------------------------------------------
print(f"\n[3/4] Running topaz extract (model=resnet8_u64, radius={PARTICLE_RAD}, threshold={THRESHOLD})...")
result = subprocess.run(
    [
        "topaz", "extract",
        "-m", MODEL,
        "-r", str(PARTICLE_RAD),
        "-t", str(THRESHOLD),
        "--format", "coord",
        "-o", coord_path,
        nor_path,
    ],
    capture_output=True, text=True,
)
print("  stdout:", result.stdout[:500] if result.stdout else "(empty)")
if result.returncode != 0:
    print("  stderr:", result.stderr[:500])
    sys.exit(1)
print(f"  Coordinates file: {coord_path}")

# ---------------------------------------------------------------------------
# Step 4 — Parse the coordinate output
# ---------------------------------------------------------------------------
print(f"\n[4/4] Parsing picks and visualising...")

# Topaz coord format: tab-separated, header "image_name\tx_coord\ty_coord\tscore"
picks_topaz = []  # list of (x_ds, y_ds, score)
try:
    with open(coord_path) as f:
        lines = f.readlines()
    print(f"  Coordinate file lines: {len(lines)}")
    if lines:
        print(f"  Header: {lines[0].rstrip()}")
    for line in lines[1:]:        # skip header
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            x_ds = float(parts[1])
            y_ds = float(parts[2])
            score = float(parts[3]) if len(parts) >= 4 else 0.0
            picks_topaz.append((x_ds, y_ds, score))
except Exception as e:
    print(f"  Could not parse coords: {e}")
    # Try CSV-like
    try:
        with open(coord_path) as f:
            lines = f.readlines()
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                x_ds = float(parts[-2])
                y_ds = float(parts[-1])
                score = float(parts[-1]) if len(parts) >= 3 else 0.0
                picks_topaz.append((x_ds, y_ds, score))
    except Exception as e2:
        print(f"  Fallback parse also failed: {e2}")

print(f"  Found {len(picks_topaz)} particles")
if picks_topaz:
    scores = [p[2] for p in picks_topaz]
    print(f"  Score range: {min(scores):.2f} – {max(scores):.2f}")

# Scale coordinates back to original image space
with mrcfile.open(IMAGE_MRC, mode='r', permissive=True) as mrc:
    orig_h, orig_w = mrc.data.shape[:2]

picks_orig = [(x * DOWN_SCALE, y * DOWN_SCALE, s) for x, y, s in picks_topaz]

# Save JSON
picks_json = [
    {"x": px, "y": py, "score": float(s), "id": f"topaz-{i}"}
    for i, (px, py, s) in enumerate(picks_orig)
]
json_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_topaz_picks.json")
with open(json_path, "w") as f:
    json.dump(picks_json, f, indent=2)

# ---------------------------------------------------------------------------
# Visualise on thumbnail
# ---------------------------------------------------------------------------
thumb_png = r"C:\magellon\gpfs\home\24dec03a\images\24dec03a_00034gr_00005sq_v01_00003hl_00018ex.png"
if os.path.exists(thumb_png):
    img_pil = Image.open(thumb_png).convert("RGB")
    th_w, th_h = img_pil.size
    sx = th_w / orig_w
    sy = th_h / orig_h
    def to_thumb(px, py):
        return int(px * sx), int(py * sy)
    radius_thumb = max(4, int(40 * sx))
else:
    with mrcfile.open(IMAGE_MRC, mode='r', permissive=True) as mrc:
        raw = mrc.data.astype(np.float32)
    lo, hi = np.percentile(raw, [1, 99])
    vis = np.clip((raw - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    img_pil = Image.fromarray(vis).convert("RGB")
    def to_thumb(px, py):
        return int(px), int(py)
    radius_thumb = 40

draw = ImageDraw.Draw(img_pil)

if picks_orig:
    scores_arr = np.array([p[2] for p in picks_orig])
    s_min, s_max = scores_arr.min(), scores_arr.max()
    def score_color(s):
        t = max(0.0, min(1.0, (s - s_min) / max(s_max - s_min, 1e-6)))
        return (int(255*(1-t)), int(255*t), 80, 220)
else:
    def score_color(s):
        return (0, 200, 80, 220)

LINE_W = max(1, radius_thumb // 8)
for i, (px, py, s) in enumerate(picks_orig):
    cx, cy = to_thumb(px, py)
    col = score_color(s)[:3]  # RGB only for draw.ellipse outline
    draw.ellipse(
        [cx - radius_thumb, cy - radius_thumb, cx + radius_thumb, cy + radius_thumb],
        fill=None,
        outline=(0, 200, 100),
        width=LINE_W,
    )
    if radius_thumb > 8:
        draw.text((cx + radius_thumb + 2, cy - 6), str(i), fill=(100, 255, 150))

# Title
draw.rectangle([0, 0, img_pil.width, 28], fill=(10, 40, 10))
draw.text(
    (8, 6),
    f"Topaz ResNet8-u64  |  {len(picks_orig)} particles  "
    f"|  threshold={THRESHOLD}  |  ds={DOWN_SCALE}x  |  radius={PARTICLE_RAD}px",
    fill=(150, 255, 150),
)

out_path = os.path.join(OUTPUT_DIR, f"{IMAGE_NAME}_topaz_picking.jpg")
img_pil.save(out_path, "JPEG", quality=90)
print(f"\nResult saved: {out_path}")
print(f"Picks JSON : {json_path}")
print(f"\n{'='*60}")
print(f"  Topaz particles : {len(picks_orig)}")
print(f"  Model           : resnet8_u64 (pretrained general)")
print(f"  Pixel size in   : 0.79 Å/px  (original)")
print(f"  Pixel size out  : {0.79 * DOWN_SCALE:.2f} Å/px  (after {DOWN_SCALE}x DS)")
print(f"{'='*60}")

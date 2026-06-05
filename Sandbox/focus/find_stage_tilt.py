"""
find_stage_tilt.py
==================
Stage Z focus — follows the README data flow exactly:

  1. correlate_shift()          -> pixel shift
  2. StageTiltMeasurement()     -> alpha + shift
  3. solve_stage_z()            -> StageZResult

Real tilt metadata from acquisition:
  4hl  — tilt = None  (untilted reference, 0.0 deg)
  3hl  — tilt = -3.0 deg
  5hl  — tilt = +3.0 deg

Usage (from Sandbox/):
    python -m focus.find_stage_tilt
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

FOCUS_DIR = Path(__file__).resolve().parent
SANDBOX_DIR = FOCUS_DIR.parent
if str(SANDBOX_DIR) not in sys.path:
    sys.path.insert(0, str(SANDBOX_DIR))

from focus.correlation import correlate_shift
from focus.z_focus import StageTiltMeasurement, solve_stage_z


def load_gray(filename: str) -> np.ndarray:
    path = FOCUS_DIR / "input_images" / filename
    with PILImage.open(path) as img:
        arr = np.asarray(img.convert("L"), dtype=np.float32)
    lo, hi = arr.min(), arr.max()
    return (arr - lo) / (hi - lo) if hi > lo else arr


STAGE_MATRIX = np.array([
    [1.0e-9, 0.0],
    [0.0,    2.0e-9],
])

img_4hl = load_gray("26jun01b_00004hl.jpg")   # untilted reference
img_3hl = load_gray("26jun01b_00003hl.jpg")   # -3.0 deg
img_5hl = load_gray("26jun01b_00005hl.jpg")   # +3.0 deg

# ── Step 1: correlate_shift -> pixel shifts ───────────────────────────────
shift_3hl = correlate_shift(img_3hl, img_4hl, taper_fraction=0.1)   # tilted vs reference
shift_5hl = correlate_shift(img_5hl, img_4hl, taper_fraction=0.1)

# ── Step 2: StageTiltMeasurement ──────────────────────────────────────────
measurements = [
    StageTiltMeasurement(alpha=math.radians(-3.0), pixel_shift=shift_3hl.shift),
    StageTiltMeasurement(alpha=math.radians(+3.0), pixel_shift=shift_5hl.shift),
]

# ── Step 3: solve_stage_z ─────────────────────────────────────────────────
result = solve_stage_z(STAGE_MATRIX, measurements)

# ── Print results ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  STAGE Z FOCUS RESULT")
print("=" * 60)
print(f"  z                = {result.z * 1e6:+.4f} um")
print(f"  z_std            = {result.z_std * 1e6:.4f} um")
print(f"  z_range          = {result.z_range * 1e6:.4f} um")
print(f"  measurement_count= {result.measurement_count}")
print()

labels = [("3hl", -3.0, shift_3hl), ("5hl", +3.0, shift_5hl)]
for idx, (label, alpha_deg, s) in enumerate(labels):
    xy = result.stage_xy[idx]
    print(f"  [{label}]  alpha={alpha_deg:+.1f} deg")
    print(f"    pixel_shift    = ({s.shift[0]:+.4f}, {s.shift[1]:+.4f}) px")
    print(f"    stage_xy       = ({xy[0]:.4e}, {xy[1]:.4e}) m")
    print(f"    z_value        = {result.z_values[idx] * 1e6:+.4f} um")
    print(f"    snr            = {s.snr:.4f}")
    print(f"    peak_ratio     = {s.peak_ratio:.4f}")
    print(f"    normalized_ccc = {s.normalized_ccc:.6f}")
    print()

print("Done.")

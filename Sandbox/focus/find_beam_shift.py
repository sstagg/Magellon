"""
find_beam_shift.py
==================
Objective-focus (beam-shift) algorithm — follows the README data flow:

  1. correlate_shift()          -> pixel shift between the two beam-tilt images
  2. BeamTiltMeasurement()      -> tilt_delta + shift
  3. solve_defocus_stig()       -> ObjectiveFocusResult

Input images are Leginon screenshots (3840x2160).
The microscope image panel is cropped out before processing.

Beam-tilt pair (from focus_runtime.example.json):
  image_1 : beam tilt (0.0,  0.0)  rad
  image_2 : beam tilt (0.01, 0.0)  rad
  tilt_delta = (0.01, 0.0)

Usage (from Sandbox/):
    python -m focus.find_beam_shift
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
from focus.objective_focus import BeamTiltMeasurement, solve_defocus_stig


def load_from_screenshot(filename: str, target_size: tuple | None = None) -> np.ndarray:
    """Load a pre-cropped beam-shift image, optionally resizing to target_size (w, h)."""
    path = FOCUS_DIR / "beamshift_input_images" / filename
    with PILImage.open(path) as img:
        gray = img.convert("L")
        if target_size is not None and gray.size != target_size:
            gray = gray.resize(target_size, PILImage.LANCZOS)
        arr = np.asarray(gray, dtype=np.float32)
    lo, hi = arr.min(), arr.max()
    return (arr - lo) / (hi - lo) if hi > lo else arr


# ── calibration matrices (from focus_calibration.example.json) ───────────
DEFOCUS_MATRIX = np.array([
    [1200.0,  30.0],
    [ -20.0, 1000.0],
])
STIGX_MATRIX = np.array([
    [200.0, -50.0],
    [ 40.0, 150.0],
])
STIGY_MATRIX = np.array([
    [ -80.0, 180.0],
    [ 160.0,  20.0],
])

# ── beam tilt values (from focus_runtime.example.json) ───────────────────
TILT_1 = (0.0,  0.0)   # rad  — image 1
TILT_2 = (0.01, 0.0)   # rad  — image 2
TILT_DELTA = (TILT_2[0] - TILT_1[0], TILT_2[1] - TILT_1[1])   # (0.01, 0.0)

# ── Step 1: load images (already cropped by user), resize to common size ─
with PILImage.open(FOCUS_DIR / "beamshift_input_images" / "Screenshot from 2026-06-01 19-20-06.png") as _i:
    size1 = _i.size
with PILImage.open(FOCUS_DIR / "beamshift_input_images" / "Screenshot from 2026-06-01 19-20-10.png") as _i:
    size2 = _i.size

common_size = (min(size1[0], size2[0]), min(size1[1], size2[1]))
print(f"  image_1 original size : {size1}")
print(f"  image_2 original size : {size2}")
print(f"  common size (for corr): {common_size}")

img1 = load_from_screenshot("Screenshot from 2026-06-01 19-20-06.png", target_size=common_size)
img2 = load_from_screenshot("Screenshot from 2026-06-01 19-20-10.png", target_size=common_size)

print(f"  image_1 shape : {img1.shape}  (beam tilt {TILT_1})")
print(f"  image_2 shape : {img2.shape}  (beam tilt {TILT_2})")
print(f"  tilt_delta    : {TILT_DELTA}")

# ── Step 2: correlate_shift -> pixel shift ────────────────────────────────
shift_result = correlate_shift(img2, img1, taper_fraction=0.1)

print()
print("=" * 60)
print("  CORRELATION (img2 vs img1)")
print("=" * 60)
print(f"  shift (row, col)  = ({shift_result.shift[0]:+.4f}, {shift_result.shift[1]:+.4f}) px")
print(f"  snr               = {shift_result.snr:.4f}")
print(f"  peak_ratio        = {shift_result.peak_ratio:.4f}")
print(f"  normalized_ccc    = {shift_result.normalized_ccc:.6f}")
print(f"  peak_value        = {shift_result.peak_value:.6f}")

# ── Step 3: BeamTiltMeasurement ───────────────────────────────────────────
measurement = BeamTiltMeasurement(
    tilt_delta=TILT_DELTA,
    pixel_shift=shift_result.shift,
)

# ── Step 4: solve_defocus_stig ────────────────────────────────────────────
# 1 measurement → defocus only (need 2 independent tilt pairs for stig)
result = solve_defocus_stig(
    DEFOCUS_MATRIX,
    [measurement],
)

print()
print("=" * 60)
print("  OBJECTIVE FOCUS RESULT")
print("=" * 60)
print(f"  defocus           = {result.defocus:.6f}  (calibration units)")
print(f"  stigx             = {result.stigx}  (needs 2nd tilt pair)")
print(f"  stigy             = {result.stigy}  (needs 2nd tilt pair)")
print(f"  residual          = {result.residual:.6e}")
print(f"  rank              = {result.rank} / {result.unknown_count}")
print(f"  condition_number  = {result.condition_number:.4e}")
print(f"  singular_values   = {result.singular_values}")
print()
print("Done.")

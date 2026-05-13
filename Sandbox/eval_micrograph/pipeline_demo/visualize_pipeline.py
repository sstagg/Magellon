"""
Walks one micrograph through every step of the eval_micrograph pipeline
and dumps an image (or plot, or text file) for each intermediate result.

Usage:
    py visualize_pipeline.py                    # default: great.png -> ./
    py visualize_pipeline.py bad1.png ../pipeline_demo_bad
    py visualize_pipeline.py empty_avg.jpg ../pipeline_demo_empty
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from micrograph_eval import eval_micrograph

parser = argparse.ArgumentParser()
parser.add_argument("input", nargs="?", default="great.png",
                    help="Image filename (resolved against project root)")
parser.add_argument("outdir", nargs="?", default=SCRIPT_DIR,
                    help="Output directory for artifacts")
args = parser.parse_args()

INPUT_NAME = args.input
INPUT_PATH = os.path.join(PARENT_DIR, INPUT_NAME)
OUT_DIR = os.path.abspath(args.outdir)
os.makedirs(OUT_DIR, exist_ok=True)


def save_fig(fname):
    path = os.path.join(OUT_DIR, fname)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close()
    print(f"  wrote {fname}")


# ------------------------------------------------------------
# Step 1: Input
# ------------------------------------------------------------
img = Image.open(INPUT_PATH)
img_gray = np.array(img.convert("L"))

plt.figure(figsize=(8, 8))
plt.imshow(img_gray, cmap="gray")
plt.title(f"Step 1: Input micrograph (grayscale) -- {img_gray.shape}")
plt.axis("off")
save_fig("01_input.png")

# ------------------------------------------------------------
# Run pipeline (gives us masks, radial profile, score)
# ------------------------------------------------------------
prob, masks, freq_Ainv, features = eval_micrograph(img_gray)
bg_mask, particle_mask, dirt_mask = masks[:, :, 0], masks[:, :, 1], masks[:, :, 2]

# ------------------------------------------------------------
# Step 2: BoxNet 3-channel segmentation
# ------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
for ax, m, name in zip(
    axes,
    [bg_mask, particle_mask, dirt_mask],
    ["Background (ch 0)", "Particle (ch 1)", "Dirt (ch 2)"],
):
    im = ax.imshow(m, cmap="viridis", vmin=0, vmax=1)
    ax.set_title(f"{name}\nmean={m.mean():.3f}")
    ax.axis("off")
    plt.colorbar(im, ax=ax, fraction=0.046)
plt.suptitle("Step 2: BoxNet output -- per-pixel class probabilities")
save_fig("02_boxnet_masks.png")

# ------------------------------------------------------------
# Step 2b: Particle mask overlaid on the raw image
# ------------------------------------------------------------
plt.figure(figsize=(10, 10))
plt.imshow(img_gray, cmap="gray")
plt.imshow(particle_mask, cmap="jet", alpha=0.4)
plt.title("Step 2b: Particle channel (channel 1) overlaid on input\n"
          "-> from here on, only this channel is used")
plt.axis("off")
save_fig("02b_particle_overlay.png")

# ------------------------------------------------------------
# Step 3: Mean subtraction (DC removal so FFT center isn't dominated by it)
# ------------------------------------------------------------
particle_mean = float(np.mean(particle_mask))
particle_centered = particle_mask - particle_mean

plt.figure(figsize=(8, 8))
vmax = np.max(np.abs(particle_centered))
plt.imshow(particle_centered, cmap="seismic", vmin=-vmax, vmax=vmax)
plt.colorbar(fraction=0.046)
plt.title(f"Step 3: Particle mask minus its mean ({particle_mean:.4f})\n"
          "(removes DC component before FFT)")
plt.axis("off")
save_fig("03_particle_centered.png")

# ------------------------------------------------------------
# Step 4: 2D power spectrum
# ------------------------------------------------------------
F = np.fft.fft2(particle_centered)
Fshift = np.fft.fftshift(F)
P = np.abs(Fshift) ** 2
P_log = np.log10(P + 1e-8)

plt.figure(figsize=(9, 9))
plt.imshow(P_log, cmap="inferno")
plt.colorbar(fraction=0.046, label="log10(power)")
plt.title("Step 4: 2D power spectrum |FFT|^2 (log10, fft-shifted)\n"
          "Center = DC (zero freq). Radius from center = spatial frequency.")
plt.axis("off")
save_fig("04_power_spectrum_2d.png")

# ------------------------------------------------------------
# Step 5: Radial average -> 256-bin 1D profile (linear scale)
# ------------------------------------------------------------
plt.figure(figsize=(11, 5.5))
plt.plot(freq_Ainv, features, color="steelblue")
plt.fill_between(freq_Ainv, features, alpha=0.2, color="steelblue")
plt.xlabel("Spatial frequency  (1/Å)")
plt.ylabel("Power  (linear)")
plt.title(f"Step 5: Radial-averaged power spectrum  ({len(features)} bins)\n"
          "Direction discarded; only frequency magnitude is kept")
plt.grid(True, alpha=0.3)
save_fig("05_radial_profile_linear.png")

# ------------------------------------------------------------
# Step 6: log + scale -> what the classifier actually consumes
# ------------------------------------------------------------
features_log = np.log(features + 1e-8)
plt.figure(figsize=(11, 5.5))
plt.plot(freq_Ainv, features_log, color="darkorange")
plt.xlabel("Spatial frequency  (1/Å)")
plt.ylabel("log(power)")
plt.title("Step 6: log-scaled radial profile  (input to MicrographCNN, before StandardScaler)")
plt.grid(True, alpha=0.3)
save_fig("06_radial_profile_log.png")

# ------------------------------------------------------------
# Step 7: Combined summary figure + score
# ------------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(18, 11))

axes[0, 0].imshow(img_gray, cmap="gray")
axes[0, 0].set_title("1. Input"); axes[0, 0].axis("off")

axes[0, 1].imshow(particle_mask, cmap="viridis", vmin=0, vmax=1)
axes[0, 1].set_title("2. BoxNet particle mask"); axes[0, 1].axis("off")

axes[0, 2].imshow(particle_centered, cmap="seismic",
                  vmin=-vmax, vmax=vmax)
axes[0, 2].set_title("3. Mean-subtracted"); axes[0, 2].axis("off")

axes[1, 0].imshow(P_log, cmap="inferno")
axes[1, 0].set_title("4. 2D power spectrum (log)"); axes[1, 0].axis("off")

axes[1, 1].plot(freq_Ainv, features, color="steelblue")
axes[1, 1].set_title("5. Radial profile (linear)")
axes[1, 1].set_xlabel("1/Å"); axes[1, 1].grid(alpha=0.3)

axes[1, 2].plot(freq_Ainv, features_log, color="darkorange")
axes[1, 2].set_title("6. Radial profile (log)  -> classifier input")
axes[1, 2].set_xlabel("1/Å"); axes[1, 2].grid(alpha=0.3)

verdict = "GOOD" if prob >= 0.5 else "BAD"
plt.suptitle(f"eval_micrograph pipeline on '{INPUT_NAME}'   "
             f"final score = {prob:.4f}  ->  {verdict}",
             fontsize=14, fontweight="bold")
save_fig("07_summary.png")

# ------------------------------------------------------------
# Step 7b: textual summary
# ------------------------------------------------------------
summary = f"""eval_micrograph pipeline -- summary
====================================

Input file        : {INPUT_NAME}
Input shape       : {img_gray.shape}
Input dtype       : {img_gray.dtype}
Input range       : [{img_gray.min()}, {img_gray.max()}]

BoxNet output (per-pixel class probability):
  background mean : {bg_mask.mean():.4f}
  particle   mean : {particle_mask.mean():.4f}
  dirt       mean : {dirt_mask.mean():.4f}

After mean subtraction:
  particle mean was : {particle_mean:.6f}
  centered range    : [{particle_centered.min():.4f}, {particle_centered.max():.4f}]

2D power spectrum (log10):
  min log power : {P_log.min():.3f}
  max log power : {P_log.max():.3f}

Radial profile  ({len(features)} bins):
  freq range (1/A)        : [{freq_Ainv.min():.4f}, {freq_Ainv.max():.4f}]
  power range  (linear)   : [{features.min():.3e}, {features.max():.3e}]
  power range  (log)      : [{features_log.min():.3f}, {features_log.max():.3f}]

CLASSIFIER OUTPUT
  probability : {prob:.6f}
  threshold   : 0.5
  verdict     : {verdict}
"""
with open(os.path.join(OUT_DIR, "07_score.txt"), "w", encoding="utf-8") as f:
    f.write(summary)
print(summary)
print(f"\nAll artifacts written to: {OUT_DIR}")

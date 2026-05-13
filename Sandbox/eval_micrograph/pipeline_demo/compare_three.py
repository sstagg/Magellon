"""
Side-by-side comparison of the three sample images through the pipeline.
Run after visualize_pipeline.py has been used on each image individually
(it's independent, but reuses the same models).
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from micrograph_eval import eval_micrograph

IMAGES = ["great.png", "bad1.png", "empty_avg.jpg"]
LABELS = ["great", "bad1", "empty_avg"]


def run(name):
    img = Image.open(os.path.join(PARENT_DIR, name))
    g = np.array(img.convert("L"))
    prob, masks, freq_Ainv, features = eval_micrograph(g)
    pm = masks[:, :, 1]
    pm_c = pm - pm.mean()
    P = np.abs(np.fft.fftshift(np.fft.fft2(pm_c))) ** 2
    return {
        "name": name,
        "img": g,
        "particle_mask": pm,
        "P_log": np.log10(P + 1e-8),
        "freq": freq_Ainv,
        "features": features,
        "features_log": np.log(features + 1e-8),
        "prob": prob,
    }


results = [run(n) for n in IMAGES]

# ---------- Figure: 4 rows x 3 cols ----------
fig, axes = plt.subplots(4, 3, figsize=(16, 18))

for col, r in enumerate(results):
    verdict = "GOOD" if r["prob"] >= 0.5 else "BAD"
    head = f"{r['name']}\nscore = {r['prob']:.3f}  ->  {verdict}"

    # Row 0: input
    axes[0, col].imshow(r["img"], cmap="gray")
    axes[0, col].set_title(head, fontweight="bold")
    axes[0, col].axis("off")

    # Row 1: particle mask
    axes[1, col].imshow(r["particle_mask"], cmap="viridis", vmin=0, vmax=1)
    axes[1, col].set_title(f"BoxNet particle mask  (mean={r['particle_mask'].mean():.3f})")
    axes[1, col].axis("off")

    # Row 2: 2D power spectrum
    axes[2, col].imshow(r["P_log"], cmap="inferno")
    axes[2, col].set_title("2D power spectrum (log)")
    axes[2, col].axis("off")

    # Row 3: 1D radial profile (log)
    axes[3, col].plot(r["freq"], r["features_log"], color="darkorange")
    axes[3, col].set_title("Radial profile (log power)  -- classifier input")
    axes[3, col].set_xlabel("1/A")
    axes[3, col].grid(alpha=0.3)
    axes[3, col].set_ylim(-2, 14)

plt.suptitle("eval_micrograph -- pipeline outputs for all three sample images",
             fontsize=15, fontweight="bold", y=0.995)
plt.tight_layout()
out_path = os.path.join(SCRIPT_DIR, "..", "pipeline_demo", "COMPARISON_all_stages.png")
out_path = os.path.abspath(out_path)
plt.savefig(out_path, dpi=110, bbox_inches="tight")
plt.close()
print(f"wrote {out_path}")

# ---------- Overlay of the three radial profiles on one axes ----------
fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
colors = ["tab:green", "tab:orange", "tab:red"]
for r, lbl, c in zip(results, LABELS, colors):
    verdict = "GOOD" if r["prob"] >= 0.5 else "BAD"
    axes[0].plot(r["freq"], r["features"], color=c,
                 label=f"{lbl}  (score={r['prob']:.3f}, {verdict})")
    axes[1].plot(r["freq"], r["features_log"], color=c,
                 label=f"{lbl}  (score={r['prob']:.3f}, {verdict})")

axes[0].set_title("Radial profile -- linear")
axes[0].set_xlabel("1/A"); axes[0].set_ylabel("power"); axes[0].grid(alpha=0.3)
axes[0].legend()

axes[1].set_title("Radial profile -- log  (this is the classifier's input)")
axes[1].set_xlabel("1/A"); axes[1].set_ylabel("log(power)"); axes[1].grid(alpha=0.3)
axes[1].legend()

plt.suptitle("Three micrographs -- one axes  (what separates the classes?)",
             fontsize=14, fontweight="bold")
plt.tight_layout()
out_path2 = os.path.join(SCRIPT_DIR, "..", "pipeline_demo", "COMPARISON_radial_overlay.png")
out_path2 = os.path.abspath(out_path2)
plt.savefig(out_path2, dpi=110, bbox_inches="tight")
plt.close()
print(f"wrote {out_path2}")

# ---------- Score table ----------
print("\nScores:")
print(f"{'image':<20}{'particle_mean':>15}{'dirt_mean':>12}{'score':>10}{'verdict':>10}")
for r in results:
    masks_means = r["particle_mask"].mean()
    # dirt is not stored, recompute quickly is wasteful; skip
    v = "GOOD" if r["prob"] >= 0.5 else "BAD"
    print(f"{r['name']:<20}{masks_means:>15.4f}{'-':>12}{r['prob']:>10.4f}{v:>10}")

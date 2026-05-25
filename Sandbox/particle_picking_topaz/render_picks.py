"""Overlay Topaz picks on the display PNGs so a human can eyeball them.

Runs run_pick on each MRC, scales the picks from MRC pixel space onto
the (downsampled) display PNG, draws a circle per pick, and writes an
annotated copy next to it.
"""
import json
import os
import sys
import time

sys.path.insert(0, "C:/projects/Magellon/plugins/magellon_topaz_plugin")

from PIL import Image, ImageDraw  # noqa: E402

from plugin.compute import run_pick  # noqa: E402

OUT_DIR = "C:/projects/Magellon/Sandbox/particle_picking_topaz/picked_overlays"
os.makedirs(OUT_DIR, exist_ok=True)

MRC_DIR = "C:/magellon/gpfs/home/24dec03a/original/"
PNG_DIR = "C:/magellon/gpfs/home/24dec03a/images/"

IMAGES = [
    "24dec03a_00031gr_00001sq_v01_00002hl_00002ex",
    "24dec03a_00031gr_00001sq_v01_00003hl_00004ex",
]

# A couple of thresholds so we can see how pick count responds.
THRESHOLDS = [-3.0, 0.0]


def render(stem: str) -> None:
    mrc = MRC_DIR + stem + ".mrc"
    png = PNG_DIR + stem + ".png"

    base = Image.open(png).convert("RGB")
    pw, ph = base.size

    for thr in THRESHOLDS:
        t0 = time.time()
        picks, shape = run_pick(mrc, model="resnet16", radius=14,
                                threshold=thr, scale=8)
        dt = time.time() - t0
        mrc_h, mrc_w = shape
        sx, sy = pw / mrc_w, ph / mrc_h

        img = base.copy()
        draw = ImageDraw.Draw(img)
        for p in picks:
            cx, cy = p["center"]
            x, y = cx * sx, cy * sy
            r = max(3.0, p["radius"] * sx * 0.5)
            draw.ellipse([x - r, y - r, x + r, y + r],
                         outline=(0, 255, 0), width=2)

        tag = f"thr{thr:+.1f}".replace("+", "p").replace("-", "m").replace(".", "")
        out = os.path.join(OUT_DIR, f"{stem}__{tag}.png")
        img.save(out)
        print(f"{stem} thr={thr}: {len(picks)} picks, {dt:.1f}s -> {out}")

        with open(os.path.join(OUT_DIR, f"{stem}__{tag}.json"), "w") as f:
            json.dump({"threshold": thr, "num": len(picks),
                       "shape": shape, "picks": picks[:50]}, f, indent=2)


if __name__ == "__main__":
    for stem in IMAGES:
        render(stem)
    print("done")

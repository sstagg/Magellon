"""Generate an all-ones float32 MRC gain reference matching the example movie shape.

The Magellon-test examples were recorded without a gain file, but the plugin's
CryoEmMotionCorTaskData requires Gain as a real path (is_mrc_file checks it).
An all-ones gain is mathematically equivalent to no gain correction — MC2
multiplies each frame pixel by 1.0, a no-op.
"""
import sys
from pathlib import Path
import numpy as np
import tifffile
import mrcfile

TIF = Path(r"C:\temp\motioncor\Magellon-test\example1").glob("*.tif")
try:
    tif_path = next(TIF)
except StopIteration:
    sys.exit("No .tif in example1/")

with tifffile.TiffFile(tif_path) as t:
    shape = t.pages[0].shape  # (H, W) or (frames, H, W)

H, W = shape[-2], shape[-1]
print(f"Movie {tif_path.name} frame dims: {H} x {W}")

gain = np.ones((H, W), dtype=np.float32)

out = Path(__file__).resolve().parents[1] / "gain_ones.mrc"
with mrcfile.new(str(out), overwrite=True) as f:
    f.set_data(gain)

print(f"Wrote {out}  ({out.stat().st_size} bytes)")

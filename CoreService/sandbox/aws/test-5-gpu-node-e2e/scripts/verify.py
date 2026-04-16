"""Verify MotionCor output MRC files are valid and reproducible.

Usage: python verify.py <outputs_dir>

Checks each .mrc file for:
  1. Valid MRC header (mrcfile can open it)
  2. Shape is 2-D or 3-D with reasonable dims (>100 px)
  3. float32 dtype
  4. All values finite
  5. Non-zero standard deviation (not a blank image)

If multiple files from the same example exist (run1 vs run2), also checks
that their pixel values match within rtol=1e-3.
"""
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import mrcfile

def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    mrcs = sorted(out_dir.glob("*.mrc"))
    if not mrcs:
        print(f"No .mrc files in {out_dir}")
        sys.exit(2)

    print(f"Found {len(mrcs)} MRC files in {out_dir}\n")

    by_example = defaultdict(list)
    all_pass = True

    for mrc_path in mrcs:
        name = mrc_path.name
        passed = True
        try:
            with mrcfile.open(str(mrc_path), mode='r', permissive=True) as f:
                data = f.data
                shape = data.shape
                dtype = data.dtype

                checks = {
                    "dims >= 2": len(shape) >= 2,
                    "min dim > 100": all(d > 100 for d in shape[-2:]),
                    "dtype float32": dtype == np.float32,
                    "all finite": bool(np.isfinite(data).all()),
                    "std > 0": float(data.std()) > 0,
                }

                status_str = "  ".join(f"{'OK' if v else 'FAIL'} {k}" for k, v in checks.items())
                overall = all(checks.values())
                tag = "PASS" if overall else "FAIL"
                print(f"[{tag}] {name}  shape={shape}  mean={data.mean():.4f}  std={data.std():.4f}")
                print(f"       {status_str}")

                if not overall:
                    passed = False

                example_key = name.split("_output")[0] if "_output" in name else name
                by_example[example_key].append((name, data.copy()))

        except Exception as e:
            print(f"[FAIL] {name}  error: {e}")
            passed = False

        if not passed:
            all_pass = False

    print()
    for key, entries in by_example.items():
        if len(entries) >= 2:
            a_name, a_data = entries[0]
            b_name, b_data = entries[1]
            if a_data.shape == b_data.shape:
                close = np.allclose(a_data, b_data, rtol=1e-3, atol=1e-4)
                max_diff = float(np.abs(a_data - b_data).max())
                tag = "PASS" if close else "FAIL"
                print(f"[{tag}] Repeatability {a_name} vs {b_name}: "
                      f"allclose={close}  max_diff={max_diff:.6f}")
                if not close:
                    all_pass = False
            else:
                print(f"[SKIP] Shape mismatch: {a_name} {a_data.shape} vs {b_name} {b_data.shape}")

    print()
    if all_pass:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Keras vs ONNX numerical parity for the exported crYOLO general model — STUB.

Mirrors topaz's parity_check.py. Pending a working `export_onnx.py`, this
script is intentionally minimal: it confirms the .h5 loads and runs end-to-end
through `pick_algorithm.process_pick`, which is the de-facto upstream ground
truth until the ONNX path is wired.

Once an ONNX model exists in weights/, extend this script to:

  1. Preprocess the test micrograph the same way crYOLO does (STANDARD norm
     + optional low-pass filter at f_c = 0.1).
  2. Run the Keras model -> raw_grid_keras (numpy)
  3. Run the ONNX model -> raw_grid_onnx (numpy)
  4. assert np.allclose(raw_grid_keras, raw_grid_onnx, atol=1e-4)
  5. Decode both with the same anchor + NMS logic and compare top-N coords.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
EXAMPLES = os.path.join(ROOT, "example_images")


def _list_h5():
    return [f for f in os.listdir(WEIGHTS) if f.lower().endswith(".h5")]


def _list_mrcs():
    if not os.path.isdir(EXAMPLES):
        return []
    return [f for f in os.listdir(EXAMPLES) if f.lower().endswith(".mrc")]


if __name__ == "__main__":
    h5s = _list_h5()
    mrcs = _list_mrcs()

    if not h5s:
        print("SKIP  no .h5 weights in weights/ — download the crYOLO general model.")
        sys.exit(0)
    if not mrcs:
        print("SKIP  no .mrc files in example_images/.")
        sys.exit(0)

    test_mrc = os.path.join(EXAMPLES, mrcs[0])
    weights = os.path.join(WEIGHTS, h5s[0])
    print(f"[upstream]  weights={h5s[0]}  image={mrcs[0]}")

    from pick_algorithm import process_pick

    try:
        picks = process_pick(test_mrc, weights=weights)
    except Exception as e:
        print(f"FAIL  cryolo_predict CLI failed: {e}")
        sys.exit(1)

    print(f"PASS  {len(picks)} picks, top score = "
          f"{picks[0]['score'] if picks else 'n/a'}")
    print()
    print("Note: this only confirms the CLI path runs. ONNX parity requires "
          "export_onnx.py and an ONNX runtime decode — both stubbed today.")

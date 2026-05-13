#!/usr/bin/env python
"""
End-to-end ONNX particle picking for crYOLO — STUB.

The vision (mirrors topaz's e2e_onnx_pick.py):

  1. Preprocess the input MRC (STANDARD norm + optional low-pass at 0.1).
  2. Forward through ONNX general model -> raw grid (numpy).
  3. Anchor-decode + NMS in numpy -> picks in original-image space.
  4. Diff against the CLI-produced picks.json (canonical upstream).

Pending export_onnx.py + a verified anchor decoder, this script just prints
the path forward.
"""
import sys


if __name__ == "__main__":
    sys.stderr.write(
        "e2e_onnx_pick.py for crYOLO is a stub. See module docstring for the\n"
        "pieces still needed: ONNX export, STANDARD/low-pass preprocessing,\n"
        "anchor decode, NMS, ground-truth diff.\n"
    )
    sys.exit(1)

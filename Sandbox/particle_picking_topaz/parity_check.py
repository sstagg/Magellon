#!/usr/bin/env python
"""
Torch vs ONNX numerical parity for the exported topaz models.

Strategy:
  1. Use topaz preprocess on the bundled test MRC -> downsampled MRC.
  2. Run the torch detector (with .eval() + .fill()) on the preprocessed
     image -> torch_scores (numpy ndarray).
  3. Run the exported ONNX detector on the same input -> onnx_scores.
  4. Assert np.allclose(torch_scores, onnx_scores).
  5. Same for denoiser on a 512x512 random crop (full denoise on the real
     micrograph would take minutes — random input is enough to confirm
     the graph is faithful).

If torch_scores == onnx_scores, the ONNX export is correct and the
downstream NMS / coord-scaling stays pure numpy regardless of which path
fed it.
"""
import os
import subprocess
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import onnxruntime as ort
import torch

import mrcfile
from topaz.model.factory import load_model as load_detector
from topaz.denoising.models import load_model as load_denoiser

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
TEST_MRC = os.path.join(
    ROOT, "example_images", "14sep05c_00024sq_00003hl_00002es_c.mrc"
)


def _topaz_exe():
    exe_dir = os.path.dirname(sys.executable)
    for name in ("topaz.exe", "topaz"):
        cand = os.path.join(exe_dir, name)
        if os.path.isfile(cand):
            return cand
    raise RuntimeError("topaz CLI not found in venv")


def preprocess_for_test(scale: int = 8) -> np.ndarray:
    """Run topaz preprocess on the bundled MRC, return the preprocessed array."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [_topaz_exe(), "preprocess", "--scale", str(scale),
             "--destdir", td, TEST_MRC],
            check=True, capture_output=True, text=True,
        )
        produced = [f for f in os.listdir(td) if f.endswith(".mrc")]
        with mrcfile.open(os.path.join(td, produced[0]), permissive=True) as m:
            return np.asarray(m.data, dtype=np.float32).copy()


def detector_parity(name: str, onnx_filename: str) -> bool:
    img = preprocess_for_test()
    print(f"  preprocessed image shape: {img.shape}  range [{img.min():.3f}, {img.max():.3f}]")

    # torch reference: load + .eval() + .fill() (mirror score_images)
    model = load_detector(name)
    model.eval()
    model.fill()
    with torch.no_grad():
        x = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).float()
        torch_scores = model(x).cpu().numpy()[0, 0]

    # ONNX
    sess = ort.InferenceSession(os.path.join(WEIGHTS, onnx_filename),
                                providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    onnx_scores = sess.run(None, {in_name: img[np.newaxis, np.newaxis]})[0][0, 0]

    if torch_scores.shape != onnx_scores.shape:
        print(f"  FAIL  shape mismatch: torch={torch_scores.shape} onnx={onnx_scores.shape}")
        return False

    diff = np.abs(torch_scores - onnx_scores)
    ok = np.allclose(torch_scores, onnx_scores, atol=1e-4)
    verdict = "PASS" if ok else "FAIL"
    print(f"  {verdict}  shape={torch_scores.shape}  max|diff|={diff.max():.3e}  "
          f"median|diff|={np.median(diff):.3e}  "
          f"score range torch=[{torch_scores.min():.3f}, {torch_scores.max():.3f}]")
    return ok


def denoiser_parity(name: str, onnx_filename: str) -> bool:
    rng = np.random.default_rng(42)
    img = rng.standard_normal((512, 512)).astype(np.float32)

    model = load_denoiser(name)
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).float()
        torch_out = model(x).cpu().numpy()[0, 0]

    sess = ort.InferenceSession(os.path.join(WEIGHTS, onnx_filename),
                                providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    onnx_out = sess.run(None, {in_name: img[np.newaxis, np.newaxis]})[0][0, 0]

    diff = np.abs(torch_out - onnx_out)
    ok = np.allclose(torch_out, onnx_out, atol=1e-4)
    verdict = "PASS" if ok else "FAIL"
    print(f"  {verdict}  shape={torch_out.shape}  max|diff|={diff.max():.3e}  "
          f"median|diff|={np.median(diff):.3e}")
    return ok


if __name__ == "__main__":
    all_pass = True

    print("[detector resnet16_u64]")
    all_pass &= detector_parity("resnet16", "topaz_resnet16_u64.onnx")
    print("[detector resnet8_u64]")
    all_pass &= detector_parity("resnet8", "topaz_resnet8_u64.onnx")
    print("[denoiser unet_L2]")
    all_pass &= denoiser_parity("unet", "topaz_unet_l2.onnx")

    print()
    print("OVERALL:", "PASS" if all_pass else "FAIL")
    sys.exit(0 if all_pass else 1)

"""onnxruntime-backed replacement for ptolemy's torch `Wrapper`.

Upstream ptolemy's ``models.py`` defines three torch models (LowMag_64x5_2ep,
BasicUNet, AveragePoolModel) plus a ``Wrapper`` class that bridges a
``nn.Module`` to the algorithms layer via ``forward_single`` /
``forward_batch`` / ``forward_cropset``.

This plugin ships the three networks as pre-exported ``.onnx`` files and
replaces ``Wrapper`` with an onnxruntime-backed one that exposes the exact
same public surface. The torch models are NOT re-defined here — callers
that used to load a ``.torchmodel`` into a ``BasicUNet`` instance should
now pass the ``.onnx`` path straight to ``Wrapper``.

Kept intentionally tiny so the plugin has no torch dependency at runtime.
"""
from __future__ import annotations

import numpy as np
import onnxruntime as ort


class Wrapper:
    """Drop-in replacement for ptolemy.models.Wrapper, onnxruntime-backed.

    Constructed with an ONNX file path (not an nn.Module).
    """

    def __init__(self, onnx_path: str, cuda: bool = False):
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if cuda
            else ["CPUExecutionProvider"]
        )
        # Disable the CPU EP's memory-arena allocator. By default it grows
        # to fit the largest input it has ever seen and never releases that
        # memory back to the OS — fine for fixed-size inputs, but this
        # session sees micrographs of varying resolution plus upscaled
        # 2048x2048 tiles from the hole-detection fallback path
        # (compute.py's _tiled_hole_detection), so the arena ratchets
        # upward across calls and never shrinks. Observed climbing past
        # 7GB RSS in ~20 minutes in production, unbounded except by
        # available host memory. Per-call allocation is slightly slower
        # than arena reuse, but bounded memory matters far more here.
        session_options = ort.SessionOptions()
        session_options.enable_cpu_mem_arena = False
        self.session = ort.InferenceSession(
            onnx_path, sess_options=session_options, providers=providers
        )
        self.input_name = self.session.get_inputs()[0].name
        self.cuda = cuda

    def to_cuda(self) -> None:
        self.cuda = True  # providers chosen at construction; no-op after init

    def to_cpu(self) -> None:
        self.cuda = False

    def _run(self, x: np.ndarray) -> np.ndarray:
        return self.session.run(
            None, {self.input_name: x.astype(np.float32, copy=False)}
        )[0]

    def forward_single(self, image):
        x = np.asarray(image)[np.newaxis, np.newaxis].astype(np.float32, copy=False)
        return self._run(x)[0, 0]

    def forward_single_scalarout(self, image):
        try:
            x = np.asarray(image)[np.newaxis, np.newaxis].astype(np.float32, copy=False)
            return float(np.asarray(self._run(x)).reshape(-1)[0])
        except Exception:
            return -100

    def forward_batch(self, batch):
        if hasattr(batch, "numpy"):
            batch = batch.numpy()  # torch tensor compat
        x = np.asarray(batch, dtype=np.float32)
        return self._run(x).flatten()

    def forward_cropset(self, cropset):
        sizes = {crop.shape for crop in cropset.crops}
        if len(sizes) == 1:
            batch = np.stack(cropset.crops, axis=0)[:, np.newaxis]
            return self.forward_batch(batch)
        results = []
        for crop in cropset.crops:
            results.append(self.forward_single_scalarout(crop))
        return np.array(results)


# Kept as a sentinel for `from ptolemy.models import BasicUNet, Wrapper` in
# algorithms.py. No methods — the vendored UNet_Segmenter uses Wrapper(onnx_path)
# directly and never instantiates this class.
class BasicUNet:
    pass


__all__ = ["Wrapper", "BasicUNet"]

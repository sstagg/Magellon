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
        self.session = ort.InferenceSession(onnx_path, providers=providers)
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

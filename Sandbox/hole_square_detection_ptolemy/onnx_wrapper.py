"""
Drop-in replacement for `ptolemy.models.Wrapper` backed by onnxruntime.

Same public methods — `forward_single`, `forward_single_scalarout`,
`forward_batch`, `forward_cropset`, `to_cpu`, `to_cuda` — so ptolemy's
algorithm code doesn't know it's not talking to PyTorch.
"""
import numpy as np
import onnxruntime as ort


class OnnxWrapper:
    def __init__(self, onnx_path, cuda=False):
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if cuda else ['CPUExecutionProvider']
        self.session = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.cuda = cuda

    def to_cuda(self):
        # ORT providers are chosen at session construction; no-op after init.
        self.cuda = True

    def to_cpu(self):
        self.cuda = False

    def _run(self, x):
        return self.session.run(None, {self.input_name: x.astype(np.float32, copy=False)})[0]

    def forward_single(self, image):
        # image is 2D HxW; add batch + channel dims, run, drop them
        x = image[np.newaxis, np.newaxis].astype(np.float32, copy=False)
        return self._run(x)[0, 0]

    def forward_single_scalarout(self, image):
        try:
            x = image[np.newaxis, np.newaxis].astype(np.float32, copy=False)
            out = self._run(x)
            # Torch's .item() works on any 1-element tensor; match that.
            return float(np.asarray(out).reshape(-1)[0])
        except Exception:
            return -100

    def forward_batch(self, batch):
        # batch may be a torch tensor or numpy array; normalise to numpy Nx1xHxW
        if hasattr(batch, 'numpy'):
            batch = batch.numpy()
        x = np.asarray(batch, dtype=np.float32)
        return self._run(x).flatten()

    def forward_cropset(self, cropset):
        # Mirror Wrapper.forward_cropset exactly: single batched run if all
        # crops share a shape, else loop.
        sizes = {crop.shape for crop in cropset.crops}
        if len(sizes) == 1:
            batch = np.stack(cropset.crops, axis=0)[:, np.newaxis]  # Nx1xHxW
            return self.forward_batch(batch)
        results = []
        for crop in cropset.crops:
            results.append(self.forward_single_scalarout(crop))
        return np.array(results)

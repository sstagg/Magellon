# BoxNet weights

Drop `boxnet.pt` here before building the Docker image (or running the
plugin via the uv install method).

Sources:

  - Warp pretrained models:        http://boxnet.warpem.com/models
  - cramerlab/boxnet repo:         https://github.com/cramerlab/boxnet
  - Same file used by the Cianfrocco-lab `eval_micrograph` tool works.

The `.pt` is a graph-trace conversion of the Warp BoxNet v2 TF model
via `onnx2torch` — `plugin/algorithm.py` re-attaches the
`flexible_forward` graph-trace at load time.

The Dockerfile COPYs the whole `weights/` directory into `/app/weights`
in the image. The plugin reads from `$BOXNET_WEIGHTS_DIR` (default
`/app/weights`) at runtime.

This file is the only thing committed under `weights/`; the `.pt`
itself is gitignored (24 MB binary; redistribution terms vary).

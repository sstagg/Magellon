# magellon-ptolemy-plugin

Magellon plugin for cryo-EM targeting, vendoring SMLC-NYSBC's [ptolemy](https://github.com/SMLC-NYSBC/ptolemy) (CC BY-NC 4.0).

## Categories

Serves two `TaskCategory` slots from one container:

| Category | Code | Input (MRC) | Output |
|---|---:|---|---|
| `SquareDetection` | 6 | Low-mag (2000–5000 Å/px) | Ranked squares + pickability score + brightness |
| `HoleDetection` | 7 | Med-mag (100–1000 Å/px) | Ranked holes + pickability score |

Both categories accept `PtolemyTaskData` ({`input_file: str`}) and return a `Detection[]` in each output envelope.

## Runtime

- **No PyTorch.** Models are pre-exported to ONNX (opset 17) and run via `onnxruntime`; container ships only the three `.onnx` files (~6 MB total).
- **Algorithms are pure numpy/scipy** (flood-fill segmentation, grid-fitting, convex hulls, Poisson-mixture segmenter — all vendored from ptolemy and unmodified).
- **BatchNorm runs in eval mode** (fixes an inference-time bug in upstream ptolemy; scores no longer depend on batch composition).

## Model provenance

The three ONNX files under `plugin/weights/` were exported from upstream's `.torchmodel` files via `Sandbox/hole_square_detection_ptolemy/export_onnx.py`. Re-generating them requires torch in the sandbox, not in the plugin.

## License

The vendored `plugin/ptolemy/` code is licensed CC BY-NC 4.0 (non-commercial). The rest of this plugin follows the Magellon repo license.

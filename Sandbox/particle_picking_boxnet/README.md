# BoxNet Cryo-EM Particle Picking

A Python tool for picking particles in high-magnitude cryo-EM micrographs using
[Warp's BoxNet v2](https://github.com/cramerlab/boxnet) — a 72-layer
fully-convolutional ResNet that produces a 3-class per-pixel mask
(background / particle / dirt). This sandbox adds a centroid-extraction step
on top of the mask so the output matches the topaz / crYOLO picker contract.

## Input

- **High-magnitude micrographs**: MRC files (BoxNet was trained on data
  downsampled to ~8 Å/pixel — pass `--scale 8` for ~1 Å/pixel originals)
- The pretrained Warp model is dataset-agnostic via heavy augmentation
- A retrained BoxNet weights file can be substituted by overriding `--weights`

Example input files go in `example_images/`.

## How to Call

### Prerequisites

```bash
pip install -r requirements.txt
```

Drop the pretrained model into `weights/`:

- `boxnet.pt`  (PyTorch-traced; this is the same file that ships under
  `eval_micrograph/boxnet.pt`)

The trace is a Warp-derived TensorFlow graph converted to PyTorch via
`onnx2pytorch`; the model expects `(B, 1, H, W)` float32 normalized per-image
to mean 0 / std 1.

### Particle picking

```bash
python pick_algorithm.py "path/to/micrograph.mrc"
```

Optional flags:

```bash
python pick_algorithm.py micrograph.mrc \
    --weights weights/boxnet.pt \
    --threshold 0.5 \
    --min-distance 14 \
    --scale 8 \
    --device auto
```

- `--weights` — path to `boxnet.pt` (auto-picked from `weights/` if exactly one
  `.pt` is present)
- `--threshold` — particle-mask probability cutoff in `[0, 1]` (default 0.5)
- `--min-distance` — minimum centre-to-centre spacing in **preprocessed** pixels
  for peak detection (default 14, mirrors topaz's NMS radius)
- `--scale` — downsample factor used to preprocess (default 8 = same as
  topaz / Warp default)
- `--device` — `cuda`, `cpu`, or `auto` (default `auto`)

### Raw 3-channel mask output

```bash
python mask_algorithm.py micrograph.mrc --output masks.npz
```

Writes a `.npz` with the three channels (`background`, `particle`, `dirt`) as
arrays of shape `(H, W)` in `[0, 1]`. Useful for:

- Debugging picker behaviour
- Downstream MICROGRAPH_QC use (the Cianfrocco-lab `eval_micrograph` tool uses
  the particle channel's radial power spectrum to score micrograph quality —
  if/when we add a `MICROGRAPH_QC` category, this is the building block)

## Output

`pick_algorithm.py` writes a JSON array to stdout — **same shape as topaz /
crYOLO** so the plugin compute layer is interchangeable:

```json
[
  {
    "center": [x, y],
    "radius": pixels,
    "score": mask_probability
  }
]
```

Coordinates are in **original-image pixel space** (multiplied by `--scale`).
Score is the value of the BoxNet particle-channel at the detected peak
(in `[0, 1]`), sorted descending.

## Benchmarking

Drop MRC inputs into `example_images/` and run:

```bash
python run_benchmarks.py
```

Outputs:

- `benchmark_outputs/picks/<example_name>.json`
- `benchmark_outputs/benchmark_summary.json`
- `benchmark_outputs/benchmark_summary.csv`

## Visualization

```bash
python visualize.py example_images/<file>.mrc --picks benchmark_outputs/picks/<file>.json
```

Optionally overlay the particle mask:

```bash
python visualize.py example_images/<file>.mrc --picks ... --mask-overlay
```

## ONNX export — viable today

Unlike crYOLO, BoxNet's `.pt` is already a torch graph — the `flexible_forward`
trick in `eval_micrograph/boxnet_utils.py` patches the forward method onto the
traced module, after which `torch.onnx.export` is one line. `export_onnx.py`
handles this; `parity_check.py` confirms torch ↔ ONNX agree on real images;
`e2e_onnx_pick.py` runs the full pipeline end-to-end through ONNX.

## Dependencies

- torch>=1.13
- numpy, scipy (peak detection)
- mrcfile, pillow, matplotlib
- onnx, onnxruntime (for ONNX export + parity)

## License

The BoxNet pretrained weights are derived from Warp (Tegunov & Cramer, *Nat
Methods* 2019). Check the upstream repo for redistribution terms; do not
commit `weights/boxnet.pt` to the Magellon repo until that is confirmed.
This wrapper is distributed under the same terms as the rest of the Magellon
sandbox.

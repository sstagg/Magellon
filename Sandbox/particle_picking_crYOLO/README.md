# crYOLO Cryo-EM Particle Picking

A Python tool for picking particles in high-magnitude cryo-EM micrographs using
the SPHIRE-crYOLO general model (Wagner et al., *Commun. Biol.* 2019, 2020).

## Input

- **High-magnitude micrographs**: MRC files with pixel size typically 0.5-2.0 Å/pixel
- Supports holey-grid micrographs and negative-stain images
- crYOLO's general model handles a wide variety of particle sizes; box size
  estimation is automatic during prediction (no anchor needed)

Example input files go in `example_images/`.

## How to Call

### Prerequisites

Install dependencies (Python 3.9 is the supported crYOLO interpreter — newer
Python versions are not yet upstream-supported):

```bash
pip install -r requirements.txt
```

Download the general model from the SPHIRE site (one of):

- `gmodel_phosnet_*.h5` (Keras / classic) — drop into `weights/`
- `gmodel_phosnet_*.onnx` (ONNX, if available) — drop into `weights/`

See https://cryolo.readthedocs.io/en/latest/installation.html for the current
download URL.

### Particle picking

```bash
python pick_algorithm.py "path/to/micrograph.mrc"
```

Optional flags:

```bash
python pick_algorithm.py micrograph.mrc \
    --weights weights/gmodel_phosnet_202005_N63_c17.h5 \
    --threshold 0.3 \
    --gpu 0
```

- `--weights` — path to the crYOLO model (`.h5` general model)
- `--threshold` — confidence cutoff in [0, 1] (default 0.3; lower = more permissive)
- `--gpu` — GPU index (`-1` forces CPU; default `0`)
- `--filament` — filament-mode picking (not the default; needs box-distance/min-box args)

## Output

`pick_algorithm.py` writes a JSON array to stdout matching the **same shape** as
the Topaz sandbox so downstream plugin code is interchangeable:

```json
[
  {
    "center": [x, y],
    "radius": pixels,
    "score": confidence
  }
]
```

Coordinates are in **original-image pixel space** (crYOLO's `.star`/`.cbox`
output is already in original coordinates). Score is the YOLO confidence
in `[0, 1]` (sorted descending).

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

Overlays the boxes onto the micrograph (no denoise pass — crYOLO is robust on
raw micrographs at this magnification).

## ONNX export — status

Unlike Topaz (pure PyTorch), crYOLO's pretrained generals ship as Keras `.h5`
files using a custom YOLOv2-style head. Direct ONNX export is non-trivial; the
canonical paths are:

1. Use `tf2onnx` against the loaded Keras model (requires TF 1.15 / 2.x with the
   matching crYOLO build).
2. Skip ONNX and call the crYOLO CLI from inside the plugin (this sandbox does
   that today — same approach as topaz uses `topaz` CLI subprocess).

`export_onnx.py` documents the tf2onnx path but is stubbed pending a real
attempt with the Keras weights in hand.

`parity_check.py` and `e2e_onnx_pick.py` are correspondingly placeholder until
the ONNX path is wired.

## Dependencies

- cryolo  (officially `pip install cryolo` with TF 2.x; see crYOLO install docs)
- numpy, mrcfile, pillow, matplotlib

## License

crYOLO is GPL-3.0 (MPI Dortmund). This wrapper is distributed under the same
terms as the rest of the Magellon sandbox.

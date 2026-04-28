# Topaz Cryo-EM Particle Picking

A Python tool for picking particles in high-magnitude cryo-EM micrographs using the
pretrained CNN models shipped with [Topaz](https://github.com/tbepler/topaz).

## Input

- **High-magnitude micrographs**: MRC files with pixel size typically 0.5-2.0 Angstroms/pixel
- Supports both holey-grid micrographs and negative-stain images
- Default preprocessing downsamples to ~8 A/pixel for the classifier

Example input files are provided in the `example_images/` directory.

## How to Call

### Prerequisites

Install dependencies (Python 3.9 recommended):

```bash
pip install -r requirements.txt
```

Topaz is installed via `topaz-em` and includes the bundled pretrained detectors
(`resnet16_u64`, `resnet8_u64`, etc.) and denoisers under
`site-packages/topaz/pretrained/`. No separate weight download is required.

### Particle picking

```bash
python pick_algorithm.py "path/to/micrograph.mrc"
```

Optional flags:

```bash
python pick_algorithm.py micrograph.mrc \
    --model resnet16 \
    --radius 14 \
    --threshold -3 \
    --scale 8
```

- `--model` — pretrained name (`resnet16`, `resnet8`, `conv63`, `conv127`) or path to a `.sav`
- `--radius` — NMS radius in preprocessed pixels (typical 8-24)
- `--threshold` — log-likelihood cutoff (`-6` permissive, `0` strict)
- `--scale` — preprocessing downsample factor (8 is standard for ~1 A/px data)

### Micrograph denoising

```bash
python denoise_algorithm.py "path/to/micrograph.mrc" --output denoised.mrc
```

Uses the Topaz-Denoise `unet` pretrained model.

## Output

`pick_algorithm.py` writes a JSON array to stdout:

```json
[
  {
    "center": [x, y],
    "radius": pixels,
    "score": log_likelihood
  }
]
```

Coordinates are in **original-image pixel space** (up-scaled from the preprocessed
image). Score is the raw classifier log-likelihood; higher is better.

`denoise_algorithm.py` writes the denoised micrograph as an MRC alongside a small
JSON summary (input/output paths, model, shape, min/max/mean stats).

## Benchmarking

Drop MRC inputs into `example_images/` and run:

```bash
python run_benchmarks.py
```

Outputs:

- `benchmark_outputs/picks/<example_name>.json`
- `benchmark_outputs/benchmark_summary.json`
- `benchmark_outputs/benchmark_summary.csv`

The script records runtime per image and the total process time.

## Dependencies

- topaz-em>=0.2.5
- torch>=1.9.0
- torchvision>=0.10.0
- numpy, scipy, pillow, matplotlib, scikit-image
- mrcfile

## License

Topaz is BSD-licensed (Bepler et al., Nature Methods 2019). This wrapper is
distributed under the same terms as the rest of the Magellon sandbox.

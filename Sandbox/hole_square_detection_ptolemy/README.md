# Ptolemy Cryo-EM Hole and Square Detection

A Python tool for detecting and scoring squares in low-magnitude cryo-EM images and holes in medium-magnitude cryo-EM images.

## Input

- **Low-magnitude images**: MRC files with pixel size around 2000-5000 Angstroms/pixel
- **Medium-magnitude images**: MRC files with pixel size around 100-1000 Angstroms/pixel
- Supports both gold and carbon holey grids, untilted grids

Example input files are provided in the `example_images/` directory.

## How to Call

### Prerequisites
Install dependencies:
```bash
pip install -r requirements.txt
```

### Low-magnitude square detection
```bash
python lowmag_algorithm.py "path/to/low_mag_image.mrc"
```

### Medium-magnitude hole detection
```bash
python medmag_algorithm.py "path/to/med_mag_image.mrc"
```

## Output

Both algorithms output JSON arrays with the following structure:

```json
[
  {
    "vertices": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
    "center": [x, y],
    "area": number,
    "score": confidence_score
  }
]
```

- `vertices`: Four corner coordinates of the detected square/hole
- `center`: Center point coordinates
- `area`: Area of the detected region
- `score`: Confidence score (0-1, higher is better)

## Benchmarking

### Example folders
Create or place benchmark MRC inputs in:

- `low_mag_examples/`
- `med_mag_examples/`

### Run all benchmarks

```bash
python run_benchmarks.py
```

This will create benchmark output files in `benchmark_outputs/`, including:

- `benchmark_outputs/low_mag/<example_name>.json`
- `benchmark_outputs/med_mag/<example_name>.json`
- `benchmark_outputs/benchmark_summary.json`
- `benchmark_outputs/benchmark_summary.csv`

The script measures the runtime for each example and records the full process total time.

## Dependencies

- torch>=1.9.0
- torchvision>=0.10.0
- numpy
- pandas
- scipy
- scikit-learn
- matplotlib
- scikit-image
- mrcfile

## License

Creative Commons Attribution-NonCommercial 4.0 International License

# Standalone Hole Finder

This package is a self-contained extraction of the classic Leginon hole-finding pipeline.

It does not import `leginon`, `pyami`, or any other project-local modules from this repository.

## Dependencies

- Python 3.9+
- `numpy`
- `scipy`

Install with:
```bash
pip install -r requirements.txt
```

## Package Layout

- `standalone_hole_finder/models.py`
- `standalone_hole_finder/edge_detector.py`
- `standalone_hole_finder/template_builder.py`
- `standalone_hole_finder/correlator.py`
- `standalone_hole_finder/thresholding.py`
- `standalone_hole_finder/blob_detector.py`
- `standalone_hole_finder/lattice.py`
- `standalone_hole_finder/lattice_fitter.py`
- `standalone_hole_finder/hole_stats.py`
- `standalone_hole_finder/ice_filter.py`
- `standalone_hole_finder/target_convolver.py`
- `standalone_hole_finder/sampler.py`
- `standalone_hole_finder/pipeline.py`

## Quick Start - Command Line

### Input

- `image.mrc`: the input cryo-EM image file to analyze
- `hole_template.mrc`: the MRC template used for template correlation

### Run template hole finder

```bash
python standalone_hole_finder_cli.py template image.mrc --template hole_template.mrc --output results.json
```

or with explicit input path:

```bash
python standalone_hole_finder_cli.py template --input image.mrc --template hole_template.mrc --output results.json
```

### Output

The CLI produces a JSON file containing the hole finder results:

- `holes`: detected hole locations and stats
- `good_holes`: filtered holes after quality checks
- `convolved_holes`: holes after template convolution
- `sampled_holes`: holes selected for sampling
- `blobs`: detected blob objects from thresholding
- `lattice`: fitted lattice information
- `correlation_stats`: correlation/threshold mask shapes
- `hole_count`: total holes found
- `good_hole_count`: total good holes

### Example

```bash
python standalone_hole_finder_cli.py template --input 26apr07a_Prld-shirin-6_00041gr.mrc --template origTemplate1.mrc --output result.json
```

## Benchmarking

Arrange benchmark examples in a hierarchical root directory. Each example folder should contain:

- `inputfile/` with one or more `.mrc` input images
- `templates/` with one or more `.mrc` template files

Example layout:

```text
input_examples/
  20may08a/
    inputfile/
      20may08a_16760340.mrc
    templates/
      origTemplate1.mrc
      origTemplate2.mrc
      origTemplate3.mrc
  21feb25a/
    inputfile/
      21feb25a_23139789.mrc
    templates/
      origTemplate1.mrc
      origTemplate2.mrc
      origTemplate3.mrc
  26apr07a/
    inputfile/
      26apr07a_Prld-shirin-6_00041gr.mrc
    templates/
      origTemplate1.mrc
      origTemplate2.mrc
      origTemplate3.mrc
```

Run the benchmark script from the package directory:

```bash
python run_benchmarks.py --example-dir input_examples --output-dir benchmark_outputs
```

If a specific example has templates, those templates are used automatically.
If the example has no templates, the script can fall back to `--template` if provided.

### Benchmark outputs

- `benchmark_outputs/<method>/<example_name>/<input_name>__<template_name>.json`
- `benchmark_outputs/benchmark_summary.json`
- `benchmark_outputs/benchmark_summary.csv`

### Benchmark command for current setup

```bash
python run_benchmarks.py --example-dir input_examples --output-dir benchmark_outputs
```

## Programmatic Usage

### 1. Edge-based hole finder

```python
from standalone_hole_finder.pipeline import run_edge_hole_finder

results = run_edge_hole_finder(
    image=image,
    template_filename="hole_edge_template.mrc",
    template_diameter=51,
    file_diameter=168,
    multiple=1,
    spacing=200.0,
    angle=25.0,
    edge_lpsig=3.0,
    edge_thresh=10.0,
    correlation_type="cross",
    correlation_filter_sigma=2.0,
    threshold_value=3.5,
    threshold_method="Threshold = mean + A * stdev",
    border=20,
    max_blobs=20,
    max_blob_size=5000,
    min_blob_size=30,
    min_blob_roundness=0.1,
    lattice_spacing=210.0,
    lattice_tolerance=0.1,
    lattice_extend="off",
    stats_radius=20,
    ice_i0=110.0,
    ice_tmin=0.0,
    ice_tmax=0.1,
    conv_vect=[(0, 0)],
    sample_classes=2,
    sample_count=2,
    sample_category="thickness-mean",
)
```

### 2. Direct template correlation hole finder

```python
from standalone_hole_finder.pipeline import run_template_hole_finder

results = run_template_hole_finder(
    image=image,
    template_filename="holetemplate.mrc",
    template_diameter=40,
    file_diameter=168,
    lattice_spacing=90.0,
)
```

## Returned Results

Both pipelines return a dictionary with these keys:

- `source_image`
- `edges` (`None` for direct template pipeline)
- `template`
- `correlation`
- `threshold_mask`
- `blobs`
- `lattice`
- `holes`
- `good_holes`
- `convolved_holes`
- `sampled_holes`

## Command Line Output

The command-line interface outputs JSON with processed results:

```json
{
  "holes": [...],
  "good_holes": [...],
  "convolved_holes": [...],
  "sampled_holes": [...],
  "blobs": [...],
  "lattice": {...},
  "correlation_stats": {...},
  "hole_count": 42,
  "good_hole_count": 38
}
```

## Notes

- Coordinates are stored as `(row, col)`.
- This package preserves the original Leginon pipeline structure, but the implementation is rewritten to be portable.
- Template files are expected to be MRC files.
- The algorithm is now standalone with no external project dependencies.

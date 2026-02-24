# Magellon Template Picker (Standalone)

Clean, Appion-independent template picker for cryo-EM.

## What it does
- Runs FindEM-like FFT template matching over angle sweeps.
- Produces normalized score maps and angle maps per template.
- Thresholds maps, extracts blob peaks, removes overlaps, and assigns particles.
- Returns coordinates and evaluative images/maps in one atomic result object.

## API
```python
from magellon_template_picker import pick_particles
```

```python
result = pick_particles(
    image=image_array,
    templates=[template1, template2],
    params={
        "diameter_angstrom": 220.0,
        "pixel_size_angstrom": 1.1,
        "bin": 1.0,
        "threshold": 0.35,
        "max_peaks": 500,
        "overlap_multiplier": 1.0,
        "angle_ranges": [(0, 360, 10), (0, 180, 5)],
    },
)
```

## Inputs
- `image`: 2D `numpy.ndarray`
- `templates`: list/tuple of 2D `numpy.ndarray`
- `params`:
  - Required:
    - `diameter_angstrom`
    - `pixel_size_angstrom`
  - Optional:
    - `bin` (default `1.0`)
    - `threshold` (default `0.4`)
    - `max_threshold` (default `None`)
    - `max_peaks` (default `500`)
    - `overlap_multiplier` (default `1.0`)
    - `max_blob_size_multiplier` (default `1.0`)
    - `min_blob_roundness` (default `0.0`)
    - `peak_position` (`"maximum"` or `"center"`, default `"maximum"`)
    - `border_pixels` (default `radius + 1`)
    - `angle_ranges` (list of `(start, end, step)` tuples)

## Outputs
`result` is a dict containing:
- `particles`: merged list of particle dicts, each with:
  - `x`, `y`, `score`, `stddev`, `area`, `roundness`, `template_index`, `angle`
- `template_results`: list with per-template maps:
  - `score_map`
  - `raw_correlation_max_map`
  - `normalization_map`
  - `angle_map`
  - `threshold_mask`
  - `particles`
- `merged_score_map`: best score at each pixel across templates
- `assigned_template_map`: template winner index map

## Dependencies
- `numpy`
- `scipy`
- `mrcfile` (for CLI MRC input/output)

## CLI
Run the picker from this project root (`magellon_template_picker/`) with:

```bash
python cli.py \
  --image /path/to/micrograph.mrc \
  --template "/path/to/origTemplate*.mrc" \
  --image-apix 1.230 \
  --template-apix 2.646 \
  --invert-templates \
  --bin 2 \
  --diameter 220 \
  --threshold 0.35 \
  --lowpass-resolution 12.0 \
  --angle-range 0,360,10 \
  --outdir /path/to/picker_output \
  --save-intermediates
```

What the CLI does:
- Bins the input image by `--bin` using true mean pooling (box averaging).
- `--bin` must be a power-of-two integer: `1, 2, 4, 8, ...` (no fractions).
- Computes target pixel size: `target_apix = image_apix * bin`.
- Rescales templates from `--template-apix` to `target_apix`.
- Optional template contrast inversion with `--invert-templates`.
- Applies optional low-pass filtering (`--lowpass-resolution`) to both image and templates.
- Runs picking and writes:
  - `particles.csv`, `particles.json`
  - `input_binned_filtered.png`
  - `input_with_template_plus_overlay.png` (larger `+` markers plus diameter circles, colored by winning template index)
  - `merged_score_map.png` (includes value scale bar and threshold marker)
  - one per-template correlation map PNG with value scale bar: `template_XXX.correlation_map.png`
  - `run_summary.json`

## Test Data Notes
For testing, use:
- `24may23b_a_00044gr_00009sq_v01_00004hl_00006ex.mrc` at `1.230 A/pix`
- `origTemplate*` at `2.646 A/pix`
- `25may06y_stack_34-37_008_X+1Y+1-2.mrc` at `0.830 A/pix`

If image and template pixel sizes differ, resample templates to match the image
pixel size before calling `pick_particles`.

Example test command with your files:

```bash
python cli.py \
  --image 24may23b_a_00044gr_00009sq_v01_00004hl_00006ex.mrc \
  --template "origTemplate*.mrc" \
  --image-apix 1.230 \
  --template-apix 2.646 \
  --invert-templates \
  --bin 1.0 \
  --diameter 220 \
  --threshold 0.35 \
  --angle-range 0,360,10 \
  --outdir picker_test_24may23b
```

And for:
- `25may06y_stack_34-37_008_X+1Y+1-2.mrc` at `0.830 A/pix`

set:
- `--image 25may06y_stack_34-37_008_X+1Y+1-2.mrc`
- `--image-apix 0.830`

Note:
- `python -m magellon_template_picker` still works when run from the parent directory.

## Interactive Threshold Viewer
Use the interactive viewer to tune CC cutoff with a slider and live pick overlay:

```bash
python viewer.py \
  --image 24may23b_a_00044gr_00009sq_v01_00004hl_00006ex.mrc \
  --template "origTemplate*.mrc" \
  --image-apix 1.230 \
  --template-apix 2.646 \
  --invert-templates \
  --bin 8 \
  --diameter 220 \
  --initial-threshold 0.35 \
  --angle-range 0,360,10 \
  --lowpass-resolution 20
```

Viewer behavior:
- Left panel: filtered image with color `+` picks (color = winning template index).
- Right panel: merged CC map with colorbar and threshold indicator.
- Bottom slider: updates picks and count in real time at different CC cutoffs.

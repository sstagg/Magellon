# Magellon Particle Picking, Stack Making, and CAN Classification Pipeline

This document describes the three standalone algorithms currently in `Sandbox`
and how their inputs and outputs are intended to connect:

1. `magellon_template_picker`
2. `magellon_stack_maker`
3. `magellon_can_classifier`

At a high level, the intended flow is:

```text
Micrograph MRC + template MRC files
  -> magellon_template_picker
  -> particles.json / particles.csv
  -> magellon_stack_maker
  -> particle_stack.mrcs + particle_stack.star
  -> magellon_can_classifier
  -> class averages, assignments, alignment tables, FRC summaries
```

## 1. `magellon_template_picker`

### Role

`magellon_template_picker` is the starting point of this pipeline. It performs
template-based particle picking on a 2D cryo-EM micrograph.

It runs FindEM-like FFT normalized template matching over one or more templates,
sweeps template rotation angles, thresholds correlation maps, extracts blob
peaks, removes overlapping picks, and returns particle coordinate candidates.

### Main Code Entry Points

- CLI: `magellon_template_picker/cli.py`
- API: `magellon_template_picker/picker.py`
- Interactive threshold tuning UI: `magellon_template_picker/viewer.py`
- API function: `pick_particles(image, templates, params)`

### Inputs

The CLI expects:

- `--image`: input micrograph `.mrc`
- `--template`: one or more template `.mrc` paths or globs
- `--image-apix`: micrograph pixel size in Angstrom per pixel
- `--template-apix`: template pixel size in Angstrom per pixel
- `--diameter`: particle diameter in Angstrom
- `--threshold`: correlation score threshold
- Optional `--bin`: power-of-two image binning factor
- Optional `--invert-templates`: invert template contrast
- Optional `--lowpass-resolution`: low-pass filter target resolution
- Optional `--angle-range`: template rotation sweep, e.g. `0,360,10`
- Optional peak filtering controls such as `--max-peaks`,
  `--overlap-multiplier`, and `--min-blob-roundness`

The API expects:

```python
result = pick_particles(
    image=image_array,
    templates=[template1, template2],
    params={
        "diameter_angstrom": 220.0,
        "pixel_size_angstrom": 1.23,
        "threshold": 0.35,
        "max_peaks": 500,
        "angle_ranges": [(0, 360, 10)],
    },
)
```

### Processing Summary

1. Reads the micrograph and template MRC files.
2. Optionally bins the micrograph.
3. Computes `target_apix = image_apix * bin`.
4. Rescales templates from `template_apix` to `target_apix`.
5. Optionally applies low-pass filtering to image and templates.
6. Runs FFT template matching for each template and angle.
7. Builds score maps and angle maps.
8. Thresholds score maps into connected blobs.
9. Converts blobs into particle picks.
10. Merges picks across templates and removes overlaps.

### Outputs

The CLI writes:

- `particles.json`: list of picked particles
- `particles.csv`: same picks in CSV form
- `run_summary.json`: picker run metadata
- `input_binned_filtered.png`: display image after preprocessing
- `input_with_template_plus_overlay.png`: pick overlay image
- `merged_score_map.png`: merged correlation map
- `template_XXX.correlation_map.png`: per-template score maps

Each particle item contains fields like:

```json
{
  "x": 123,
  "y": 456,
  "score": 0.42,
  "stddev": 0.03,
  "area": 37,
  "roundness": 0.81,
  "template_index": 1,
  "label": "template_1",
  "angle": 70.0
}
```

### Output Contract For The Next Stage

`magellon_stack_maker` can consume `particles.json` or `particles.csv` because
it requires at least `x` and `y`, and tolerates additional fields such as
`score`, `angle`, and `class_number`.

Important coordinate note:

- If `magellon_template_picker` runs with `--bin 1`, the output coordinates are
  in the original micrograph pixel coordinate system.
- If it runs with `--bin 2`, `--bin 4`, etc., the picks are in the binned image
  coordinate system. Before giving those picks to `magellon_stack_maker` with
  the original full-resolution micrograph, coordinates must be multiplied by
  the bin factor, or stack making must run against the same binned image.

## 2. `magellon_stack_maker`

### Role

`magellon_stack_maker` converts picked particle coordinates into boxed particle
images and RELION-style metadata. It bridges coordinate picking and downstream
2D classification.

It reads a micrograph plus particle coordinates, extracts fixed-size boxes,
normalizes each extracted particle using edge statistics, and writes a particle
stack and metadata.

### Main Code Entry Points

- CLI: `magellon_stack_maker/cli.py`
- API: `magellon_stack_maker/stack_maker.py`
- API function: `build_and_write(...)`

### Inputs

The CLI expects:

- `--micrograph`: input micrograph `.mrc`
- `--particles`: picked particle JSON or CSV
- `--particles-format`: optional explicit `json` or `csv`
- `--box-size`: even integer box size in pixels
- `--edge-width`: edge width for per-particle background normalization
- `--micrograph-apix`: optional pixel size in Angstrom per pixel
- `--micrograph-name`: optional override for STAR metadata
- `--ctf-json`: optional CTF metadata lookup
- `--outdir`: output directory
- `--star-output`: STAR filename
- `--json-output`: companion JSON filename
- `--stack-output`: optional `.mrcs` particle stack filename

The coordinate input must be a list of dictionaries with at least:

```json
[
  {
    "x": 123.4,
    "y": 456.7,
    "score": 0.91,
    "angle": 45.0,
    "class_number": 1
  }
]
```

CSV input must contain `x` and `y` columns. Additional columns are carried when
recognized.

### Processing Summary

1. Loads the micrograph MRC as a 2D image.
2. Loads picked particles from JSON or CSV.
3. Converts each pick into a typed particle coordinate.
4. Extracts a square box centered on each `x`, `y` coordinate.
5. Allows or rejects partial boxes depending on `--allow-partial`.
6. Normalizes each box using edge-pixel mean and standard deviation.
7. Pads partial boxes after normalization when partial boxes are allowed.
8. Writes the normalized particle stack if `--stack-output` is provided.
9. Writes RELION-style STAR metadata.
10. Writes a JSON companion file with particle metadata.

### Outputs

The CLI can write:

- `particle_stack.mrcs`: normalized boxed particles
- `particle_stack.star`: RELION-style particle metadata
- `particle_stack.json`: companion metadata JSON

The STAR file includes columns such as:

- `_rlnImageName`
- `_rlnMicrographName`
- `_rlnCoordinateX`
- `_rlnCoordinateY`
- `_rlnClassNumber`
- `_rlnAutopickFigureOfMerit`
- `_rlnAngleRot`
- Optional CTF columns:
  - `_rlnDefocusU`
  - `_rlnDefocusV`
  - `_rlnDefocusAngle`
  - `_rlnVoltage`
  - `_rlnSphericalAberration`
  - `_rlnPhaseShift`
  - `_rlnAmplitudeContrast`
- Optional pixel size column currently written as `_rlnPixelSize`

### Output Contract For The Next Stage

`magellon_can_classifier` is intended to consume the generated `.star` file.
The STAR rows should point to particle images in the generated `.mrcs` stack
through `_rlnImageName`.

For smooth classifier consumption, the STAR should use RELION image tokens in
this form:

```text
000001@particle_stack.mrcs
000002@particle_stack.mrcs
...
```

The classifier resolves these paths relative to the STAR file location.

## 3. `magellon_can_classifier`

### Role

`magellon_can_classifier` performs standalone particle preprocessing,
alignment, CAN topology classification, MRA alignment to CAN references, class
average generation, and optional high-resolution phase-flip averaging.

It is the final algorithm in the current standalone pipeline.

### Main Code Entry Points

- CLI: `magellon_can_classifier/cli.py`
- Core algorithm: `magellon_can_classifier/classifier.py`
- API function: `run_align_and_can(...)`

### Inputs

The CLI accepts either:

- Primary input: `--star` RELION particle STAR file
- Fallback input: `--stack` `.mrc` or `.mrcs` particle stack

Other important inputs:

- `--apix`: pixel size in Angstrom per pixel, required unless available in STAR
- `--outdir`: output directory
- `--max-particles`: optional particle count limit
- `--lowpass-resolution`: optional low-pass filter resolution
- `--fft-scale`: Fourier-domain image scaling factor
- `--invert`: invert particle contrast
- `--phase-flip-ctf`: apply CTF phase flipping from STAR metadata
- `--num-classes`: target CAN class count
- `--num-presentations`: CAN training steps
- `--learn`, `--ilearn`, `--max-age`: CAN learning parameters
- `--align-iters`: topology iterations, each running CAN then MRA
- `--threads`: preprocessing and MRA threading
- `--can-threads`: CAN assignment and averaging threading
- `--compute-backend`: `cpu`, `torch-auto`, `torch-cuda`, `torch-mps`, or
  `torch-cpu`

### Processing Summary

1. Reads particles from STAR, resolving `_rlnImageName` entries to stack paths
   and 1-based particle indices.
2. Falls back to reading `--stack` directly if no STAR is supplied.
3. Derives pixel size from STAR metadata or uses `--apix`.
4. Optionally reads per-particle CTF metadata from STAR.
5. Preprocesses particles:
   - optional contrast inversion
   - optional low-pass filtering
   - optional centering
   - optional normalization
   - optional Fourier scaling
   - optional CTF phase flipping
6. Runs topology iterations:
   - CAN classification on the current particle stack
   - MRA alignment to CAN class-average references
   - class-average generation
   - warm-starts the next CAN pass from MRA averages
7. Writes final class averages, assignments, alignment tables, and summaries.

### Outputs

The classifier writes outputs such as:

- `preprocessed_stack.mrcs`
- `aligned_stack.mrcs`, only if `--write-aligned-stack` is enabled
- `class_averages.mrcs`
- `node_vectors.mrcs`
- `can_class_averages_iter001.mrcs`, `can_class_averages_iter002.mrcs`, etc.
- `mra_class_averages_iter001.mrcs`, `mra_class_averages_iter002.mrcs`, etc.
- `iteration_mra_iter001.json`
- `iteration_mra_iter001.star`
- `iteration_mra_iter001.txt`
- `assignments.csv`
- `class_counts.csv`
- `class_averages_highres_phaseflip.mrcs`
- `frc_highres_phaseflip/`
- `run_summary.json`
- `iteration_history.json`
- `can_checkpoint_history.json`

`assignments.csv` links particle index to class assignment, final rotation, MRA
reference assignment, and MRA reference score.

## End-To-End Example

The following shows the intended sequence. Paths and parameters should be
adapted to the dataset.

### Step 1: Template Picking

```bash
python -m magellon_template_picker \
  --image /data/micrograph.mrc \
  --template "/data/templates/origTemplate*.mrc" \
  --image-apix 1.230 \
  --template-apix 2.646 \
  --invert-templates \
  --bin 1 \
  --diameter 220 \
  --threshold 0.35 \
  --angle-range 0,360,10 \
  --outdir /work/picker_output
```

Primary output for the next step:

```text
/work/picker_output/particles.json
```

### Step 2: Stack Making

```bash
python -m magellon_stack_maker \
  --micrograph /data/micrograph.mrc \
  --particles /work/picker_output/particles.json \
  --box-size 256 \
  --edge-width 2 \
  --micrograph-apix 1.230 \
  --outdir /work/stack_output \
  --star-output particle_stack.star \
  --json-output particle_stack.json \
  --stack-output particle_stack.mrcs
```

Primary outputs for the next step:

```text
/work/stack_output/particle_stack.star
/work/stack_output/particle_stack.mrcs
```

### Step 3: CAN Classification

```bash
python -m magellon_can_classifier \
  --star /work/stack_output/particle_stack.star \
  --apix 1.230 \
  --outdir /work/can_output \
  --num-classes 50 \
  --num-presentations 200000 \
  --align-iters 3 \
  --threads 8 \
  --can-threads 8 \
  --compute-backend torch-auto
```

Primary outputs:

```text
/work/can_output/class_averages.mrcs
/work/can_output/assignments.csv
/work/can_output/class_counts.csv
/work/can_output/run_summary.json
```

## Current Integration Issues To Resolve

The three algorithms form a coherent pipeline conceptually, but the current
code has contract mismatches that developers should address before treating the
pipeline as plug-and-play.

### 1. STAR `_rlnImageName` Token Order

`magellon_stack_maker` currently writes `_rlnImageName` like:

```text
particle_stack.mrcs@000001
```

`magellon_can_classifier` currently parses `_rlnImageName` as:

```text
000001@particle_stack.mrcs
```

This means the classifier will interpret `particle_stack.mrcs` as the index and
fail. The preferred fix is to make stack maker write RELION-style tokens:

```text
000001@particle_stack.mrcs
```

Relevant code:

- `magellon_stack_maker/stack_maker.py`: `_format_image_token(...)`
- `magellon_can_classifier/cli.py`: `_resolve_image_path(...)`

### 2. Pixel Size Column Name

`magellon_stack_maker` currently writes pixel size as:

```text
_rlnPixelSize
```

`magellon_can_classifier` currently looks for:

```text
_rlnImagePixelSize
```

Until this is fixed, pass `--apix` explicitly to the classifier. The preferred
contract fix is to make stack maker emit `_rlnImagePixelSize`, or make the
classifier accept both names.

Relevant code:

- `magellon_stack_maker/stack_maker.py`: `write_relion_star(...)`
- `magellon_can_classifier/cli.py`: `_derive_star_apix(...)`

### 3. Binned Picker Coordinates

When template picker runs with `--bin > 1`, output coordinates are based on the
binned image. Stack maker currently assumes coordinates directly match the
micrograph passed to `--micrograph`.

Developer options:

- Keep `--bin 1` for end-to-end pipeline runs.
- Scale picker coordinates back to original image coordinates before stack
  making.
- Teach stack maker about the picker bin factor and scale internally.
- Write and pass the binned micrograph to stack maker instead of the original
  micrograph.

### 4. `class_number` Is Optional In Picker Output

Stack maker accepts `class_number` but defaults it to `1` when absent. Template
picker emits `template_index` and `label`, not `class_number`. This is currently
acceptable, but if developers want template identity to carry into STAR
`_rlnClassNumber`, add an explicit mapping from `template_index` to
`class_number`.

## Recommended Developer Contract

For the cleanest pipeline contract:

1. Template picker should write particle coordinates in full-resolution
   micrograph coordinates, or include explicit coordinate metadata:
   `coordinate_apix`, `source_bin`, and `coordinate_frame`.
2. Stack maker should write RELION-compatible `_rlnImageName` tokens as
   `000001@particle_stack.mrcs`.
3. Stack maker should write `_rlnImagePixelSize` when pixel size is available.
4. Classifier should tolerate both `_rlnImagePixelSize` and `_rlnPixelSize` for
   robustness.
5. All three stages should write a small `run_summary.json` that includes the
   exact files intended for the next stage.

With those fixes, the pipeline becomes:

```text
picker_output/particles.json
  -> stack_maker --particles

stack_output/particle_stack.star
  -> can_classifier --star

stack_output/particle_stack.mrcs
  -> referenced by _rlnImageName inside the STAR
```

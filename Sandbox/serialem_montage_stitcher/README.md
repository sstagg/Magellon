# SerialEM Montage Stitcher

This helper script stitches montage images from a SerialEM `medium_mag` import.
It parses `.mrc.mdoc` metadata files for `MontSection` and `ZValue` entries,
then assembles montage pieces using the same coordinate-based stitching logic
used in the SerialEM import path.

## Setup

### 1. Prepare an Input Folder

Create a folder to hold your SerialEM montage data. You need **two files per montage**:
- `.mrc` file (the image data)
- `.mrc.mdoc` file (the metadata)

**Example folder structure:**
```
my_montage_data/
  MMM_4mgml_g1.mrc
  MMM_4mgml_g1.mrc.mdoc
  sample_grid_2.mrc
  sample_grid_2.mrc.mdoc
```

### 2. Run the Stitcher

```bash
python serialem_montage_stitcher.py --medium-dir my_montage_data
```

This will discover all `.mrc` and `.mrc.mdoc` file pairs and stitch them into the `stitched_montages/` folder.

## Inputs

Your input folder should contain:
- One or more `.mrc` image files from SerialEM
- Matching `.mrc.mdoc` metadata files with the same base name
  - Example: `sample.mrc` must have a corresponding `sample.mrc.mdoc`

## Outputs

The script generates:
- One stitched `.mrc` file per montage group
- Output files are written to `stitched_montages/` by default (or custom path with `--output-dir`)
- Files are named `<original_name>_<navigator_label>.mrc`

**Example output:**
Given input files `MMM_4mgml_g1.mrc` and `MMM_4mgml_g1.mrc.mdoc`, the script produces:

```
stitched_montages/
  MMM_4mgml_g1_4.mrc
  MMM_4mgml_g1_5.mrc
  MMM_4mgml_g1_6.mrc
  ...
  MMM_4mgml_g1_19.mrc
```

Each output file represents one montage group from the `.mdoc` metadata.

## Command-Line Options

- `--medium-dir` *(required)*: Path to folder containing `.mrc` and `.mrc.mdoc` files
- `--output-dir`: Directory for stitched output montages (default: `stitched_montages`)
- `--option`: Piece coordinate option to use for stitching
  - `PieceCoordinates` (raw piece coordinates)
  - `AlignedPieceCoords` (aligned coordinates, **default**)
  - `AlignedPieceCoordsVS` (aligned with microscope stage information)

## Usage Examples

**Basic usage (files in current directory):**
```bash
python serialem_montage_stitcher.py --medium-dir .
```

**Custom output directory:**
```bash
python serialem_montage_stitcher.py --medium-dir my_montage_data --output-dir my_results
```

**Use different coordinate alignment:**
```bash
python serialem_montage_stitcher.py --medium-dir my_montage_data --option PieceCoordinates
```

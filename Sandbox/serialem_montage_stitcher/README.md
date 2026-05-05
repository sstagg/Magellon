# SerialEM Montage Stitcher

This helper script stitches montage images from a SerialEM `medium_mag` import.
It parses `.mrc.mdoc` metadata files for `MontSection` and `ZValue` entries,
then assembles montage pieces using the same coordinate-based stitching logic
used in the SerialEM import path.

## Quick Start

```bash
python serialem_montage_stitcher.py --medium-dir . --output-dir stitched_montages
```

This will discover all `.mrc` and `.mrc.mdoc` file pairs in the current directory
and stitch them into the `stitched_montages/` folder.

## Inputs

- `--medium-dir`: path to the SerialEM `medium_mag` directory (or any folder with `.mrc`/`.mrc.mdoc` pairs)
- `.mrc` image files inside the directory
- matching `.mrc.mdoc` metadata files with the same base name

## Outputs

- one stitched `.mrc` file per montage group
- output files are written to `stitched_montages/` by default
- files are named `<original_name>_<navigator_label>.mrc`

## Example

Given `MMM_4mgml_g1.mrc` and `MMM_4mgml_g1.mrc.mdoc`, the script produces:

```
stitched_montages/
  MMM_4mgml_g1_4.mrc
  MMM_4mgml_g1_5.mrc
  MMM_4mgml_g1_6.mrc
  ...
  MMM_4mgml_g1_19.mrc
```

Each output file represents one montage group from the `.mdoc` metadata.

## Options

- `--medium-dir`: Input directory containing `.mrc` and `.mrc.mdoc` files (required)
- `--output-dir`: Output directory for stitched montages (default: `stitched_montages`)
- `--option`: Piece coordinate option: `PieceCoordinates`, `AlignedPieceCoords`, or `AlignedPieceCoordsVS` (default: `AlignedPieceCoords`)

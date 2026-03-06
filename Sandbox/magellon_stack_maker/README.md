# magellon_stack_maker

Atomic code for building particle stacks from a micrograph and coordinate picks.

## What it does

- Loads micrograph pixel data (MRC).
- Loads picking coordinates (JSON or CSV).
- Extracts fixed-size boxes per pick.
- Applies per-particle normalization using edge-box statistics (`mean`/`std` from edges).
- Optionally writes a RELION-ready stack (`.mrcs`) from normalized particles.
- Writes RELION `.star` metadata and JSON metadata with the same rows.
- Supports future CTF integration through optional CTF JSON lookup.

## CLI

```bash
python cli.py \
  --micrograph /path/to/micrograph.mrc \
  --particles /path/to/picking.json \
  --box-size 256 \
  --edge-width 2 \
  --outdir outputs \
  --star-output particles.star \
  --json-output particles.json \
  --stack-output particles_stack.mrcs
```
`--box-size` must be an even integer.

## Coordinate format

### JSON

Must be a list of dictionaries with at least:

```json
[{"x": 123.4, "y": 200.7, "score": 0.91, "angle": 45.0, "class_number": 1}]
```

### CSV

Must contain headers including `x` and `y` columns. Additional optional columns (`score`, `angle`, `class_number`) are read if present.

## CTF integration

`--ctf-json` accepts:

- A dict keyed by micrograph name:

```json
{
  "micrograph_00001.mrc": {
    "defocus_u_angstrom": 15000,
    "defocus_v_angstrom": 16000,
    "defocus_angle_deg": 90,
    "voltage_kv": 300,
    "spherical_aberration_mm": 2.7,
    "phase_shift_deg": 0,
    "amplitude_contrast": 0.07
  }
}
```

- A list of dicts keyed per-item by `micrograph_name`:

```json
[{"micrograph_name":"micrograph_00001.mrc","defocus_u_angstrom":15000}]
```

These fields are emitted into optional CTF columns in the STAR file.

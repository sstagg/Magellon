# Magellon CAN Classifier (Standalone)

Standalone `alignment + CAN classification` for Relion particle STAR inputs (or stack fallback).

## Inputs
- Primary: Relion particle STAR file (`--star`)
- Fallback: particle stack `.mrc` / `.mrcs` (`--stack`)
- Pixel size from STAR (`_rlnImagePixelSize`) or explicit `--apix`

## Pipeline
1. Optional preprocessing: invert, low-pass, centering, normalization
2. Optional CTF phase flip correction
3. Iterative topology loop:
   - CAN classification
   - MRA alignment to CAN references (skimage polar)
4. Class assignment + class average output

## Run
From this directory:

```bash
python cli.py \
  --star /path/to/particles.star \
  --max-particles 10000 \
  --threads 8 \
  --can-threads 8 \
  --compute-backend torch-auto \
  --num-classes 50 \
  --num-presentations 200000 \
  --learn 0.01 \
  --ilearn 0.0005 \
  --max-age 25 \
  --align-iters 3 \
  --lowpass-resolution 20 \
  --outdir can_output
```

## CTF Phase Flip
When `--phase-flip-ctf` is enabled, CTF is read from STAR metadata only:
- Defocus from `_rlnDefocusU`/`_rlnDefocusV` (per particle).
- Voltage from `_rlnVoltage`.
- Spherical aberration from `_rlnSphericalAberration`.
- Amplitude contrast from `_rlnAmplitudeContrast`.

No manual/global CTF overrides are used.

Notes:
- `--phase-flip-ctf` requires `--star`.
- `--apix` is optional if STAR has `_rlnImagePixelSize` (particles or optics table).
- Phase-flip sign now follows EMAN convention (`CTF_SIGN = sign(cos(gamma - acac))`).
- `--max-particles` limits to the first N particles (useful for quick tests).
- `--threads` controls per-particle preprocessing/alignment threading.
- `--can-threads` controls threaded CAN post-training assignment and class averaging.
- `--compute-backend` controls CAN math backend and accelerates `skimage-polar` MRA candidate evaluation when torch device is available: `cpu`, `torch-auto`, `torch-cuda`, `torch-mps`, `torch-cpu`.

## Outputs
- `preprocessed_stack.mrcs`
- `aligned_stack.mrcs` (optional; write only with `--write-aligned-stack`)
- `class_averages.mrcs` (from scaled/filtered preprocessed particles)
- `can_class_averages_iter001.mrcs`, `can_class_averages_iter002.mrcs`, ... (CAN stage per iteration)
- `mra_class_averages_iter001.mrcs`, `mra_class_averages_iter002.mrcs`, ... (MRA stage per iteration)
- `class_averages_highres_phaseflip.mrcs` (from unscaled/unfiltered phase-flipped particles, replaying final transforms)
- `node_vectors.mrcs`
- `assignments.csv`
- `class_counts.csv` (high-res average/half counts)
- `frc_highres_phaseflip/` (per-class FRC curves + summary for high-res phase-flip averages)
- `run_summary.json`

Class-average postprocessing:
- Class averages are recentered by translational phase correlation to a rotationally averaged mean reference, before mask application.
- Disable with `--no-center-averages`.

# Cryo-EM Ice Thickness (MeasureIce-style)

A Python tool for estimating ice thickness in cryo-EM micrographs via
the **aperture-limited scattering (ALS)** approach of MeasureIce
(Olson et al., *Commun Biol* 5, 911, 2022).

## The physics

Through ice of thickness `t`, the un-scattered (or scattered-but-not-
removed-by-the-aperture) intensity follows Beer-Lambert:

    I(t) = I₀ · exp(-t / T_eff)

so

    t = -T_eff · ln(I / I₀)

where:
  - `I₀` is the vacuum-reference intensity (no sample in the beam)
  - `T_eff` is the *effective* mean-free-path. It depends on:
      - accelerating voltage (200 kV vs 300 kV)
      - the objective aperture's half-angle in mrad (the actual physics
        is set by which scattering angles are *removed*, not by the
        aperture's micron diameter)

The sandbox uses real MeasureIce HDF5 LUTs `(intensity_ratio → thickness_nm)`
produced by running upstream `Generate_MeasureIce_calibration.py` against
the bundled `supercooled_water.xyz` atomic model. A scalar `T_eff` fallback
exists for the unconfigured path; you should never need it. See
`luts/README.txt` for how to regenerate the LUT for other microscopes.

T_eff (= ALS coefficient λ) is **strongly aperture-dependent**. At 300 kV,
from the multislice simulation:

| Aperture (mrad) | Aperture (µm label) | λ = T_eff (nm) |
|---:|---:|---:|
| 5  | 50  |  447 |
| 10 | 70  |  647 |
| 15 | 100 |  858 |  ← default
| 20 | 140 | 1092 |

(λ values are from the 0–1500 nm LUT; they differ ~10 % from the 0–600 nm
slope-fit values printed by the upstream generator because Beer-Lambert
deviates at large thicknesses. The LUT itself, not the scalar, is what
the sandbox uses.)

## Three operating modes

| Mode | Inputs | What you get |
|---|---|---|
| **single-image, percentile I₀** | one MRC | per-pixel `t` map, using the 99th-percentile intensity in the image as the vacuum proxy. Best for *relative* thickness ranking when you don't have a true reference. |
| **single-image, ROI I₀** | one MRC + `(x, y, w, h)` of a known-vacuum region | per-pixel `t` map calibrated against an actual no-sample region. The MeasureIce paper's intended use. |
| **reference-image I₀** | one MRC + a reference MRC of an empty grid square | full quantitative thickness, microscope-calibrated. |

## How to call

```bash
# Single image; defaults: bundled Krios_300kV.h5 LUT @ 15 mrad (100 µm aperture)
python measure_thickness.py path/to/micrograph.mrc

# Override aperture (e.g. 70 µm objective aperture ≈ 10 mrad)
python measure_thickness.py path/to/micrograph.mrc --aperture-mrad 10

# Use an explicit vacuum ROI instead of the 99.9th-percentile fallback
python measure_thickness.py path/to/micrograph.mrc --i0-mode roi --i0-roi 100,100,80,80

# Scalar fallback (only if you do not have a LUT)
python measure_thickness.py path/to/micrograph.mrc --lut '' --t-eff 858

# Batch a directory with the default regime gate (5-500 Å/px in-frame)
python analyze_dir.py /c/magellon/gpfs/24dec03a/home/original \
    --aperture-mrad 15 \
    --output-dir analysis_outputs/
```

## Output

For each input MRC:
  - `<stem>_thickness.npy` — float32 (H, W) array of thickness in nm
  - `<stem>_thickness.png` — heatmap overlay for review
  - one row in `summary.csv`:
        image, I0_used, mean_t_nm, median_t_nm, p95_t_nm,
        thin_frac (% pixels < 30 nm), thick_frac (% > 100 nm)

## Caveats

1. The dataset in `C:\magellon\gpfs\24dec03a\home\original` is **atlas-
   level** imagery (2718 Å/px — whole-grid images). MeasureIce was
   designed for **medium-mag hole imagery** (~50-500 Å/px) where vacuum
   and ice are both clearly visible in one frame. At atlas level our
   thickness map is a relative quality signal across the grid, not an
   absolute per-hole thickness.

2. The percentile-I₀ fallback assumes the brightest 1% of pixels are
   near-vacuum. On a heavily ice-covered grid this is wrong. Use ROI
   or reference-image mode whenever possible.

3. Saturated pixels (typical sensor saturation > 4000 counts on Falcon
   detectors) are clipped before the log; report a sanity flag in
   `summary.csv` so you can spot detector clipping.

## Provenance

The algorithm is the simplest faithful implementation of the MeasureIce
ALS approach. References:

  - Olson et al., *Commun Biol* 5, 911 (2022).
    https://www.nature.com/articles/s42003-022-03698-x
  - Rice et al., *Acta Cryst D* 74, 644 (2018) — classical ice thickness
    measurement procedure.

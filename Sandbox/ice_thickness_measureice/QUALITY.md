# MeasureIce sandbox — quality assessment, 24dec03a dataset

This document is the result of two passes:
  1. An initial scalar-T_eff run over 308 MRCs at all magnification levels
     (kept for historical reference at the bottom).
  2. A corrected LUT-based run that reflects how MeasureIce is actually
     supposed to be used. **This is the result to trust.**

## Setup

  * Cloned upstream MeasureIce + py_multislice, ran their
    `Generate_MeasureIce_calibration.py` end-to-end against their
    `supercooled_water.xyz` atomic model.
  * Generated `luts/Krios_300kV.h5` covering 5/10/15/20 mrad apertures
    and 0–1500 nm thickness.
  * Default aperture: **15 mrad** (≈100 µm objective aperture, λ ≈ 858 nm).
    Override per session via `--aperture-mrad`.
  * `session.json` ground truth: **300 kV, Cs = 2.7 mm**. Aperture not
    recorded in the session export.

## Run

    python analyze_dir.py C:/magellon/gpfs/24dec03a/home/original \
        --output-dir analysis_outputs_v2 --no-png

The script now:
  * filters to MeasureIce's valid magnification regime (5–500 Å/px) —
    only hole-preview frames pass for this dataset (19 / 308);
  * skip-lists `diagnostic_*.mrc` sentinels;
  * uses the HDF5 LUT for ratio→thickness instead of a single scalar;
  * decouples the saturation cap from the I_0 percentile.

## Results (LUT-based, 15 mrad / 100 µm aperture)

| Metric | Value |
|---|---|
| Images processed (in-regime hole-preview) | 19 / 308 |
| I_0 CV across the 19 frames | **5.1 %** ✅ |
| Median(median_t) | **606 nm** |
| Median(mean_t)   | **548 nm** |
| thin_frac (<30 nm) median | 0.3 % |
| thick_frac (>100 nm) median | 98.6 % |

### Interpretation

The ice in this session is uniformly thick by cryo-EM standards — every
in-regime frame reports **~500–700 nm**, with no frame thinner than
~470 nm. That falls into one of two readings:

  1. **The objective aperture is smaller than 15 mrad.** If the actual
     aperture is 10 mrad (≈70 µm), the same data divides cleanly into
     numbers near 380–500 nm — still thick, but no longer at the LUT
     ceiling. We do not have the aperture in `session.json`; the operator
     for this session would have to confirm.
  2. **The grids really are over-iced.** The dataset was used in
     prior pipelines as a worked example for atlas/square/hole imaging
     hierarchy testing, not as a "good ice for high-res" reference.
     The I_0 stability across 19 frames (5.1 %) is consistent with
     "uniformly thick ice" rather than "wrong I_0".

The honest output is: **no good targets in this dataset by MeasureIce's
ALS metric**. That matches the visual character of the hole frames.

## Why the original analysis showed 196 nm median

The first pass processed all 308 MRCs (atlas / square / hole / focus /
exposure) with a single scalar T_eff = 395 nm.

  * 395 nm is the simulation-derived λ for a **5 mrad** aperture — much
    smaller than typical Krios setups. Applied to a 15 mrad-aperture
    dataset it underestimates thickness by ≈2×.
  * 218 of 308 frames were `*ex.mrc` single-particle exposures at
    0.79 Å/px. At that magnification the frame is entirely inside one
    hole — no vacuum visible — so the 99.9th percentile of the image
    intensities was just "slightly less ice," not vacuum. The numbers
    happened to land in a physically plausible range because of the
    scalar T_eff, not because the measurement was meaningful.
  * The "I_0 CV 2.8 %" stability claim was the percentile being stable,
    not I_0 being correct.

Net: the original 196 nm median was an artefact of (i) wrong λ for the
implied aperture, (ii) inputs outside the valid magnification range,
(iii) percentile→vacuum being false at high mag.

## What was changed in the code

  * `measure_thickness.py`
    - Added `load_lut(path, aperture_mrad)` that loads the upstream
      HDF5 format and returns a `scipy.interpolate.interp1d` ratio→nm.
    - `compute_thickness` now accepts either `t_eff_nm=` (scalar) or
      `lut_interp=` (LUT).
    - Saturation clip is `--saturation-percentile` (default 99.99),
      no longer aliased to the I_0 percentile.
    - CLI defaults to the bundled LUT at 15 mrad.

  * `analyze_dir.py`
    - Pixel-size gate `[--min-apix, --max-apix]` (5–500 Å/px) with
      out-of-regime frames silently skipped.
    - `SKIP_PATTERNS = ("diagnostic_",)` to drop sentinel images.
    - CSV columns extended: `pixel_size_A`, `method`,
      `lut_aperture_mrad`, `lut_lambda_nm`.

## CTFFIND5 cross-validation (2026-05-13) — MeasureIce overestimates by 5-18×

CTFFIND5 v5.0.2 was set up in `../ice_thickness_ctffind5/` and run on
9 representative exposures across 5 holes. 5 of 9 had a reliable
CTF fit (CC > 0.1); the other 4 are fit failures, not real readings.

| Hole | CTFFIND5 (nm) | This sandbox @ 15 mrad (nm) | Gap |
|---|---|---:|---:|
| 31gr/01sq/03hl | **35.0, 38.8, 34.9** | 696 | **18×** |
| 34gr/03sq/03hl | 42.5 | 548 | 13× |
| 34gr/05sq/03hl | 115.0 | 651 | 5.7× |

The 24dec03a dataset is **actually mostly thin ice (35-115 nm)** —
good cryo-EM ice. Both the original sandbox (196 nm) and this LUT
revision (548-651 nm) were wrong. The root cause is the percentile-99.9
I_0 fallback: on hole-preview frames of thin ice, the brightest 0.1%
of pixels are contamination/hot-pixels, not vacuum. There is no
vacuum-vs-ice intensity gap at 35 nm thickness (the predicted ratio
is 0.96 at 15 mrad — a 4% gap that the noise floor swamps).

Full diagnosis: `../ice_thickness_ctffind5/COMPARISON.md`.

### Implications for using this sandbox

  * **Do not trust the percentile-99.9 fallback for absolute
    thickness on thin-ice frames.** Use it only for relative ranking
    of frames that share the same vacuum/contamination character.
  * For absolute thickness, either:
      - acquire a true vacuum image and pass `--i0-mode reference`, or
      - hand-pick a vacuum ROI and pass `--i0-mode roi`.
  * For per-exposure thickness during processing, use CTFFIND5 instead.

## Outstanding follow-ups

  * Aperture confirmation for this session (operator query) — would
    pin the absolute thickness numbers within ±10 %.
  * If pipeline-integrated: gate dispatch on hole-preview level inputs
    (apix in [5, 500]) and emit a warning when the thickness clamps to
    the LUT's upper bound.
  * Consider hiding the percentile-99.9 mode as the default for
    automated pipelines — make ROI / reference required.

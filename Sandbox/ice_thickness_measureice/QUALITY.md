# MeasureIce sandbox — quality assessment on `24dec03a` dataset

**Run:** `python analyze_dir.py C:/magellon/gpfs/24dec03a/home/original
--preset 300kV --i0-percentile 99.9 --output-dir analysis_outputs --no-png`

**Total:** 308 MRCs processed in 249 s (~0.81 s/image, no PNG).

The `24dec03a` dataset contains the full magnification hierarchy in one
directory — atlas (`*gr.mrc`), grid square (`*sq*`), hole preview
(`*hl*`), exposure (`*ex*`), and focus (`*fc*`). MeasureIce is designed
for **hole-preview / exposure / focus** scale where both ice and clean
vacuum are visible in one frame; the README's caveat that atlas/square
imagery is not a good fit is borne out below.

## Stratified summary

| Level | n | I₀ CV | median t | thin (<30 nm) | thick (>100 nm) | verdict |
|---|---:|---:|---:|---:|---:|---|
| `fc` (focus)    | 17  | **4.3 %** | **167 nm** | 0.6 % | 88 % | ✅ algorithm working as designed |
| `ex` (exposure) | 218 | **2.8 %** | **194 nm** | 0.6 % | 92 % | ✅ algorithm working as designed |
| `hl` (hole)     | 19  | **5.2 %** | **299 nm** | 0.5 % | 90 % | ✅ frame covers wider area → higher avg, still plausible |
| `sq` (square)   | 10  | 3.0 %   | 1367 nm   | 0.8 % | 96 % | ⚠ no clean vacuum at this scale (predicted) |
| `gr` (atlas)    | 43  | 16 %    | 1491 nm   | 0.7 % | 98 % | ⚠ no clean vacuum + variable framing |
| `diag` (junk)   | 1   | —       | 0 / 357 nm| 51 %  | 47 %  | sentinel — `diagnostic_output.mrc` |

I₀ CV = `σ(I₀) / mean(I₀)` over the images at that level. Under 15 %
means the percentile-99.9 fallback for vacuum reference is producing
a stable I₀ across that subset — a precondition for treating relative
thickness rankings as meaningful.

## What the numbers say

1. **At hole / exposure / focus scale, the algorithm is reliable.**
   I₀ stability is 2.8–5.2 % CV — well inside the 15 % threshold. Median
   thickness 167–299 nm is in the physically plausible range for
   cryo-EM ice; the upper end (~300 nm at hole preview) reflects that
   the frame covers more of the support film than the bowl of one hole.

2. **The 218 `ex` exposures are immediately actionable for targeting.**
   With I₀ stable to 2.8 % across them, ranking by per-image
   `median_t_nm` reliably surfaces the thinnest acquisition areas. The
   thinnest 5 exposures from the dataset live around 165–175 nm; the
   thickest stretch to 230 nm. That spread is well-resolved by the
   measurement.

3. **`gr` and `sq` outputs are NOT to be trusted as absolute
   thickness.** The percentile-99.9 fallback for I₀ degrades when no
   true vacuum is in the frame; at atlas scale (2718 Å/px) the brightest
   pixels are bare-grid edges or saturated diagnostic tags, both of
   which violate the "clean vacuum" assumption. The README spelled this
   out before the run; the data confirms it.

4. **The `diagnostic_output.mrc` outlier** is a stamped sentinel image
   (I₀ ≈ 2) — ignore it and consider adding `**/diagnostic_*.mrc` to a
   skip-list in `analyze_dir.py` for cleaner batch runs.

## Representative thickness maps

`analysis_outputs/representative/` contains four hand-picked PNGs:

| Tag | Image | I₀ | median t |
|---|---|---:|---:|
| atlas    | `24dec03a_00001gr.mrc`                                  | 1297  | 1148 nm |
| focus    | `…_00031gr_00001sq_v01_00003hl_00001fc.mrc`              | 9151  | 159 nm  |
| exposure | `…_00034gr_00005sq_v01_00003hl_00010ex.mrc`              | 808   | 194 nm  |
| hole     | `…_00034gr_00005sq_v01_00004hl.mrc`                      | 8776  | 318 nm  |

The atlas + hole PNGs make the geometry clear: at atlas scale the
algorithm has no clean reference; at hole scale you can see ice-filled
bowls (~150–200 nm) against support-film bars (~400+ nm) — exactly the
contrast MeasureIce was designed to surface.

## What this validates for the plugin path

The sandbox numbers above are the green light to lift this into a
plugin. Three suggested guardrails for the plugin manifest:

1. **Recommended input level**: hole-preview MRC (`*hl*`) or exposure
   (`*ex*`). Reject atlas at dispatch time, or at least flag results
   from atlas-scale images as non-quantitative.
2. **Default `T_eff` = 395 nm** (300 kV preset). Surface a typed input
   field so the operator can override per microscope.
3. **Default I₀ mode**: `percentile` with `--i0-percentile 99.9` for
   batch / dispatch flows; expose `roi` and `reference` modes for
   higher-fidelity per-job runs.

## Outstanding follow-ups

- LUT integration: today we approximate MeasureIce's HDF5 LUT with a
  single scalar `T_eff`. Good to ~10 %. For full per-mrad-aperture
  accuracy, integrate the real LUTs from
  https://github.com/HamishGBrown/MeasureIce — `scipy.interpolate.interp1d`
  over a 1-D `(ratio → thickness)` table is the swap.
- Pair with Ptolemy: feed Ptolemy's per-hole `(center, radius)` records
  into a per-hole `mean(t)` aggregation so each hole gets a thickness
  scalar alongside its existing `score`.
- Skip-list for synthetic / diagnostic frames (e.g.
  `diagnostic_output.mrc`).

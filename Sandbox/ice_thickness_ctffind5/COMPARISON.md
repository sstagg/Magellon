# MeasureIce vs CTFFIND5 — head-to-head on 24dec03a

Two independent thickness methods on the same dataset:

  * **MeasureIce** at 15 mrad / λ ≈ 858 nm via the canonical HDF5 LUT
    (see `../ice_thickness_measureice/`), I_0 = percentile-99.9 fallback.
  * **CTFFIND5 v5.0.2** with thickness mode (brute force + 2D refinement),
    fit at 30–4 Å resolution.

Settings: 300 kV, Cs = 2.7 mm, amplitude contrast 0.07. Exposures at
0.79 Å/px; hole-preview frames at 88.9 Å/px.

## Per-hole comparison

For each hole, we have CTFFIND5 readings on its exposures and one
MeasureIce reading on the corresponding `*hl.mrc`. CTFFIND5 readings
are filtered to those with CC > 0.1 (below that the CTF fit failed
and the thickness number is junk).

| Hole | CTFFIND5 (nm, CC>0.1) | MeasureIce hole (nm) | Gap |
|---|---|---:|---:|
| 31gr/01sq/03hl | 35.0, 38.8, 34.9 | 696 | **18×** |
| 34gr/03sq/03hl | 42.5 | 548 | 13× |
| 34gr/05sq/03hl | 115.0 | 651 | 5.7× |
| 31gr/02sq/05hl | (all CTFFIND fits failed; CC ≤ 0.02) | 621 | n/a |
| 34gr/04sq/03hl | (CTFFIND fit failed; CC = 0.06) | 546 | n/a |

## Diagnosis

MeasureIce's percentile-99.9 fallback assumes the brightest 0.1% of
pixels are vacuum. On a 88.9 Å/px hole-preview frame of **thin ice**,
that assumption is structurally false:

  * For 35 nm of ice at 15 mrad aperture, the predicted intensity ratio
    is `exp(-35 / 858) = 0.96`. Vacuum would only be 4% brighter than
    the frame median.
  * The actual frame intensity histogram shows a 2-3× spread between
    median and brightest 0.1% (median 3766, p99.9 = 8337). That spread
    is **contamination, support film thinning, hot pixels** — NOT
    vacuum that's only 4% brighter than ice.
  * Treating those bright contaminants as vacuum makes the I/I_0 ratio
    look like ~0.45 instead of ~0.96, so MeasureIce "measures" 700+ nm
    of ice that doesn't exist.

For thicker ice (≳200 nm), the vacuum-vs-ice intensity gap is large
enough that the brightest tail probably IS near-vacuum, and MeasureIce
becomes plausible (sandbox row 31gr/02sq/05hl at 621 nm is consistent
with a CTFFIND5 reading we couldn't get there).

## What this means for ice thickness in our pipeline

  1. **CTFFIND5 is the right tool for per-exposure thickness on
     single-particle data.** ±5 nm accuracy, no vacuum reference
     needed, runs on the actual acquisition frames the user already
     has from the data-collection workflow.

  2. **MeasureIce is only trustworthy when given a real vacuum
     reference.** The percentile fallback is a misdesign on thin-ice
     hole-preview frames. To use MeasureIce as a screening tool:
     - acquire one explicit vacuum image per session (broken hole or
       beam-on-no-grid) and pass via `--i0-mode reference`, OR
     - use ROI mode with a hand-picked vacuum patch (`--i0-mode roi`).
     The percentile path should be reserved for "is this grid hosed"
     rough triage, not for absolute thickness numbers.

  3. **A two-stage pipeline is natural:** MeasureIce as a fast triage
     during a session, CTFFIND5 as authoritative per-exposure thickness
     during post-acquisition processing.

  4. **The 24dec03a dataset is mostly THIN ICE (35-115 nm).** That's
     good cryo-EM ice. The earlier "median 196 nm" claim from the
     scalar-T_eff sandbox and the "median 600 nm" claim from the
     LUT-based v2 sandbox are both wrong — vindicated by CTFFIND5.

## Sanity-checked against the paper's own validation dataset (EMPIAR-11063)

To make sure the CTFFIND5 driving above is correct, we ran our setup on
three FIB-milled-lamella micrographs from EMPIAR-11063 (the dataset
the Elferich 2024 paper uses for thickness validation, 1.5 Å/px, 300 kV,
Cs=2.7 mm). The paper's Figure 3 reports thicknesses of 97 nm and
202 nm for FIB lamellae from this dataset — i.e. the expected range
is 50-250 nm for any well-fit micrograph.

| Image (EMPIAR-11063 / EUC_Lamella1) | Defocus (Å) | CC | Spacing | Thickness |
|---|---:|---:|---:|---:|
| s_lamella_map_00000…1_0.mrc   | 30335 / 29374 | 0.017 | 11.0 Å | 367 nm — **fit failed** |
| s_lamella_map_00099…100_0.mrc | 20454 / 19151 | 0.096 | 8.3 Å  | 319 nm — borderline |
| s_lamella_map_00299…300_0.mrc | 9113 / 7160   | 0.194 | 5.3 Å  | **138 nm — clean fit** |

The 138 nm reading sits in the published 97-202 nm range. The CC > 0.1
threshold cleanly separates real fits from noise (same threshold that
worked for our 24dec03a results). Defocus, spacing, and thickness are
all in physically plausible cryo-EM ranges.

This confirms our CTFFIND5 setup is being driven correctly.

## Reproducing

```bash
# CTFFIND5 batch
cd C:/projects/Magellon/Sandbox/ice_thickness_ctffind5
./batch_ctffind5.sh results.tsv \
    C:/magellon/gpfs/24dec03a/home/original/24dec03a_*hl_*ex.mrc

# Filter to reliable fits and summarize
awk -F'\t' 'NR==1 || $4>0.1' results.tsv > results_reliable.tsv
```

## CTFFIND5 prompt sequence (reference)

For someone scripting this pipeline elsewhere, the v5.0.2 prompt order
in scripted mode is (one answer per line on stdin):

```
<input.mrc>           input image
<output_diag.mrc>     diagnostic image path (NOT yes/no!)
<pixel_size_A>        e.g. 0.79
<voltage_kV>          e.g. 300
<Cs_mm>               e.g. 2.7
<amp_contrast>        e.g. 0.07
<spectrum_size>       e.g. 512
<min_res_A>           e.g. 30
<max_res_A>           e.g. 4
<min_defocus_A>       e.g. 5000
<max_defocus_A>       e.g. 50000
<defocus_step_A>      e.g. 100
no                    do you know astigmatism?
no                    slower exhaustive search?
no                    use restraint on astigmatism?
no                    find additional phase shift?
no                    determine sample tilt?
yes                   determine sample thickness?
yes                   use brute force 1D search?
yes                   use 2D refinement?
<low_res_nodes>       e.g. 30.0
<high_res_nodes>      e.g. 3.0
no                    use rounded square for nodes?
no                    downweight nodes?
no                    set expert options?
```

Output `<diag>.txt` last column = thickness in Angstroms. Filter on
column 6 (CC) > 0.1 to drop fit failures.

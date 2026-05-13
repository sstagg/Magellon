# CTFFIND5 thickness sandbox

Per-exposure ice-thickness estimation from CTF Thon-ring oscillation
(Elferich et al., *eLife* 2024). **Accuracy: ±5 nm** on single-particle
exposures — i.e. the regime where MeasureIce explicitly fails.

This sandbox is the complement to `../ice_thickness_measureice/`:

| | MeasureIce (ALS) | CTFFIND5 (Thon-rings) |
|---|---|---|
| Hardware | none | none |
| Mag regime | 5–500 Å/px (hole/exposure preview) | ≤ 1 Å/px (acquisition frames) |
| Vacuum reference needed | yes | no |
| Per-frame accuracy | ~10 % | ±5 nm |
| Typical use | grid screening, target selection | per-exposure quality post-acquisition |

## One-time setup

1. **Get the CTFFIND5 binary.** The cisTEM tarball that bundles
   CTFFIND5 is 1.87 GB; download it once and extract only the binary:

   ```bash
   curl -L -o /tmp/cistem.tar.gz \
       https://grigoriefflab.umassmed.edu/sites/default/files/cisTEM-ctffind5-b21db55.tar.gz
   tar tzf /tmp/cistem.tar.gz | grep -E '/ctffind$'   # find the right path
   tar xzf /tmp/cistem.tar.gz <path-to-ctffind> -C .
   mv <extracted-dir>/ctffind ./ctffind
   chmod +x ./ctffind
   ```

   The extracted binary goes here next to the Dockerfile.

2. **Build the runtime image.**

   ```bash
   docker build -t ctffind5:latest .
   ```

   This is a thin Ubuntu 22.04 + runtime libs image (~120 MB). The
   binary is mounted in at run time, not baked in.

## Per-image usage

```bash
./run_ctffind5.sh /c/magellon/gpfs/24dec03a/home/original/<some_ex.mrc>
```

The script writes `results/<stem>.txt` with CTFFIND5's full diagnostic;
the script prints just the thickness line.

## Where the thickness comes from

CTFFIND5 fits a thickness-aware modulation envelope on top of the
classic CTF Thon-ring model. The thickness manifests as a beating
pattern in the rings — thicker ice damps high-resolution rings faster.
The fit returns a single thickness value per image to ±5 nm.

This is **not** the same physics as MeasureIce: MeasureIce uses
aperture-limited inelastic scattering on un-filtered intensities;
CTFFIND5 uses elastic-scattering interference visible in the power
spectrum. They are independent measurements — agreement between the
two on the same frame is a strong consistency check.

## Cross-validation plan

  * Run MeasureIce (`../ice_thickness_measureice/`) on a hole-preview
    frame, e.g. `*_00003hl.mrc` from a target square.
  * Run CTFFIND5 (this sandbox) on the matched exposures
    `*_00003hl_*ex.mrc` taken in that hole.
  * Expected: median CTFFIND5 thickness across the exposures should
    lie within ±10 % of the MeasureIce hole-level thickness. A larger
    gap implies (a) wrong aperture setting in MeasureIce, or (b) a
    thickness gradient across the hole that MeasureIce averaged over.

## Status

  * Dockerfile + `run_ctffind5.sh` are ready.
  * Binary download is the only remaining step (large download — see
    one-time setup). After that:
    1. extract `ctffind` next to the Dockerfile
    2. `docker build -t ctffind5:latest .`
    3. `./run_ctffind5.sh <mrc>` on a few exposures
    4. compare against `../ice_thickness_measureice/analysis_outputs_v2/summary.csv`

## References

  * Elferich, J., Kong, S., Zhang, X., Grigorieff, N. (2024). CTFFIND5
    provides improved insight into quality, tilt and thickness of TEM
    samples. *eLife* 13:RP97227.
    https://elifesciences.org/articles/97227

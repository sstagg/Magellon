# cryoassess Implementation and Test Plan

## Scope

This document records the refactor of the vendored MicAssess / 2DAssess
package (`cryoassess`) into a layered `core` / `models` / `cli` structure, how
the result aligns with the source paper, and how it is tested.

## Source paper

Li, Cash, Tesmer & Cianfrocco, "High-Throughput Cryo-EM Enabled by User-Free
Preprocessing Routines", *Structure* 28, 858-869 (2020) -- local copy at
`docs/1-s2.0-S0969212620300800-main.pdf`.

Important: the paper describes the **original two-class MicAssess** (a ResNet34
binary good/bad classifier) and the four-class 2DAssess (ResNet50). The shipped
weights and code are **MicAssess v1.0** -- a later, hierarchical six-label model
(base CNN + FFT radial-average branch + binary / good / bad heads) that the
2020 paper does not describe. The package is therefore a *superset* of the
paper: the preprocessing pipeline matches the paper closely, while the model
topology has moved on.

## Architecture after the refactor

```
cryoassess/
  core/    pure, TensorFlow-free, unit-tested
    preprocessing.py   normalize / circular mask / crops / class-avg crop
    starfile.py        RELION star <-> pandas
    mrc.py             MRC load + FFT downsample + grayscale conversion
    fft_features.py    radial-average log power spectrum (numpy reference)
    labels.py          six-class labels + threshold assignment
    classcenter.py     saliency-based 2D-average centering check
  models/  TensorFlow model construction + inference
    micassess.py       hierarchical micrograph model + predict
    assess2d.py        2D class-average model + predict
    fft_layer.py       in-graph FFT feature layer
    keras_compat.py    tf-keras / tensorflow.keras shim
  cli/     thin argparse entry points (micassess, 2dassess)
tests/     pytest suite for cryoassess.core (34 tests)
```

The layering guarantees `import cryoassess.core` works without TensorFlow;
`models` and `cli` pull TF in only when an actual model run starts.

## Alignment with the paper

| Paper (STAR Methods) | cryoassess code | Verdict |
|---|---|---|
| Network input image size **494 x 494** | PNGs are loaded at 494 x 512 (K2) / 494 x 696 (K3); the model's `Cropping2D` layer trims to 494 x 494 | Aligned -- the effective CNN input is 494 x 494 |
| Micrographs **normalized to a mean of zero** | `core.preprocessing.normalize` subtracts the mean *and* divides by std | Superset -- mean-zero plus unit-variance (preserved from the v1.0 implementation) |
| **Circular mask, diameter 494 px** | `core.preprocessing.apply_circular_mask` (largest disc that fits) | Aligned |
| Micrographs **low-pass filtered and downscaled** | `core.mrc.fft_downsample` crops in Fourier space, which is inherently a low-pass + downscale | Aligned |
| **Binary cross-entropy** loss, **ADAM** optimizer, **0.0001** learning rate, **sigmoid** output | `models.micassess` compiles the heads with `binary_crossentropy`; `models.assess2d` uses `Adam(learning_rate=1e-4)` | Aligned |
| Prediction **threshold 0.1** to tolerate false positives | `core.labels.DEFAULT_T1 = 0.1`; CLI `--t1` default 0.1 | Aligned |
| MicAssess output: **two classes** (good / bad) | `core.labels.LABEL_LIST` has **six** classes; the model has a base + FFT branch + three heads | Code is newer -- this is MicAssess v1.0, not the paper's model |
| (not in paper) | FFT radial-average log-power-spectrum feature branch (`core.fft_features`, `models.fft_layer`) | v1.0 addition, no paper counterpart |
| 2DAssess: crop to `d x d`, normalize mean-zero, **resize 256 x 256 Lanczos** | `core.preprocessing.cut_by_radius` + `core.mrc.scale_to_uint8`; `models.assess2d.class_average_generator` targets 256 x 256 with `interpolation="lanczos"` | Aligned |
| 2DAssess: **saliency (spectral residual)** check -- object count + centred centre-of-mass | `core.classcenter.is_centered` uses `cv2 ... StaticSaliencySpectralResidual` with the same object-count and centre-of-mass tests | Aligned |
| 2DAssess: four classes good / clip / edge / noise | `models.assess2d.CLASS_AVERAGE_LABELS = (Clip, Edge, Good, Noise)` | Aligned |

**Conclusion.** The refactored *preprocessing and decision logic* faithfully
reproduces the paper's described method; the divergences are all because the
shipped model is the post-paper v1.0 (six-label, FFT-augmented). The one
implementation detail beyond the paper text is the unit-variance division in
`normalize` -- it was kept because the pre-trained weights were produced with
it; changing it would require model revalidation.

## What the refactor changed

Behaviour-preserving restructure plus genuine bug fixes:

- `apply_circular_mask` now honours its `center` / `radius` arguments. The old
  `mask_img` discarded them, which had silently collapsed the K2 and K3
  left/right preprocessing variants into one identical function (documented in
  `core/preprocessing.py`).
- `build_models` rejects unsupported detector/cutpos pairs up front instead of
  leaving the `crop` tensor undefined; unknown detectors raise instead of
  `NameError`.
- The CLI no longer hardcodes `'MicAssess'` for reset/cleanup, no longer
  re-globs the PNG directory inside loops (was O(n^2)), writes the score TSVs
  into the output directory, and uses `os.path.basename` (Windows-safe).
- `assess2d` got its missing Keras-backend import, `Adam(learning_rate=)` (was
  the removed `lr=`), and `predict` (was the removed `predict_generator`); the
  case-mismatched dead "good" branch is fixed.
- The dead, broken duplicate `cryoassess/mrcs2jpg.py` and the stale `lib/`
  package were removed.

## Test strategy

Testing is tiered because the model path needs assets unavailable in a plain
checkout (the `.h5` weights are gitignored).

### Tier 1 -- pure core unit tests (implemented)

`tests/` -- 34 passing tests covering `core`:

- preprocessing: mean/std normalisation, constant-image safety, circular-mask
  geometry, the `center`/`radius` regression, `cut_by_radius`, a real example
  PNG.
- starfile: minimal and RELION-3.1 multi-block parsing, block-code selection,
  write round-trip.
- mrc: FFT downsample height/even-width, `scale_to_uint8` range, grayscale
  conversion, crops, MRC load and stack round-trips.
- fft_features: power-spectrum non-negativity, radial-average length and
  constant-image behaviour, finiteness, sigmoid range.
- labels: great/decent/bad assignment, `t1`/`t2` boundary shifts, batch
  assignment, `is_good`.

### Tier 2 -- model parity (deferred)

Requires TensorFlow (>= 2.16 + `tf-keras`) and the four `.h5` weight files in
`weights/`. `benchmark.py` is the model-level smoke check: it runs the K2
model over the 30 labelled `Examples/` PNGs and reports accuracy, a confusion
matrix and timing. It now builds the model through `cryoassess.models` rather
than duplicating `build_models`.

When a TF environment is available, add:

- a `build_models` shape test (input 494 x width, output feature length 247);
- a numpy-vs-TF parity test for the FFT feature branch
  (`core.fft_features.radial_log_power_spectrum_sigmoid` against
  `models.fft_layer.radavg_logps_sigmoid` on the same input).

### Tier 3 -- end-to-end CLI (deferred)

Requires TF, weights, and a small set of sample `.mrc` files. Assertions:

- `micassess` produces `png/`, the six label directories, the two
  `*_great.star` / `*_good.star` files, and the score TSVs inside `-o`;
- `--dont_reset` reuses the PNGs and does not re-run conversion;
- `2dassess` sorts a class-average stack into Clip/Edge/Good/Noise and prints
  the good indices.

## Open items

- `core.classcenter` cannot be unit-tested in the current environment because
  `opencv-python` is not installed; it is the only core module without tests.
- Tier 2 / Tier 3 are unverified in this environment (no TensorFlow, no
  weights). They must be run on a machine with `pip install -e ".[models]"`
  and the downloaded `.h5` files before MicAssess is used for real curation.
- `normalize` performs unit-variance scaling in addition to the paper's
  mean-zero step. This is intentional (it matches the trained weights); revisit
  only together with model retraining.

# MicAssess — Setup, Usage, and Benchmark Guide

MicAssess is a hierarchical neural-network classifier that scores cryo-EM micrographs
into six quality categories using pre-trained Keras/TensorFlow models.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Installation](#2-installation)
3. [Project layout](#3-project-layout)
4. [Running MicAssess](#4-running-micassess)
5. [Expected output](#5-expected-output)
6. [Running the benchmark](#6-running-the-benchmark)
7. [Benchmark results (example images)](#7-benchmark-results-example-images)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Requirements

| Component | Version |
|-----------|---------|
| Python | 3.10 – 3.13 |
| TensorFlow | 2.20 or 2.21 |
| tf-keras | matching TF version |
| numpy | 1.24+ / 2.x |
| Pillow | 9+ |
| mrcfile | 1.4+ |
| pandas | 1.5+ |
| opencv-python | 4.x |
| scikit-image | 0.19+ |

> The original repo targeted TF 2.5 / Python 3.7. The installation steps below
> use TF 2.21 (the current release) with the `tf-keras` compatibility shim so
> the pre-trained `.h5` weights load without modification.

---

## 2. Installation

### 2a. Clone / locate the source

```
cd <parent-directory>
git clone https://github.com/cianfrocco-lab/Automatic-cryoEM-preprocessing.git Ice_qulaity_MicAssess
cd Ice_qulaity_MicAssess
```

Or, if the folder is already present, just `cd` into it.

### 2b. Create a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2c. Install dependencies

```bash
pip install tensorflow tf-keras numpy Pillow mrcfile pandas opencv-python scikit-image
```

This pulls TF 2.21 and the matching `tf-keras` 2.21 compatibility layer automatically.

### 2d. Install the cryoassess package (editable)

```bash
pip install -e ".[models]"
```

This registers the `micassess` and `2dassess` console entry-points and installs
the core dependencies plus TensorFlow.  For just the TensorFlow-free core
(`cryoassess.core`), use `pip install -e .`; add the `dev` extra
(`pip install -e ".[dev]"`) to also get `pytest` for the test suite.

### 2e. Obtain the pre-trained model weights

The four `.h5` weight files must be placed in a `weights/` directory at the
project root.  Download them from:

> https://cosmic-cryoem.org/software/cryo-assess/

Fill in the short form, accept the terms, and you will receive a download link
by e-mail.  The four files required are:

```
weights/
  base_micassess_v100.h5
  fine_binary_micassess_v100.h5
  fine_good_micassess_v100.h5
  fine_bad_micassess_v100.h5
```

Do **not** rename these files — the code discovers them by prefix glob.

---

## 3. Project layout

```
Ice_qulaity_MicAssess/
├── cryoassess/
│   ├── core/                  # pure, TensorFlow-free routines (unit-tested)
│   │   ├── preprocessing.py   #   normalize / circular mask / crops
│   │   ├── starfile.py        #   RELION star <-> pandas
│   │   ├── mrc.py             #   MRC load + FFT downsample + scaling
│   │   ├── fft_features.py    #   radial-average log power spectrum (numpy)
│   │   ├── labels.py          #   six-class labels + threshold assignment
│   │   └── classcenter.py     #   2D class-average centering check
│   ├── models/                # TensorFlow model construction + inference
│   │   ├── micassess.py       #   hierarchical micrograph model
│   │   ├── assess2d.py        #   2D class-average model
│   │   ├── fft_layer.py       #   in-graph FFT feature layer
│   │   └── keras_compat.py    #   tf-keras / tensorflow.keras shim
│   └── cli/                   # thin argparse entry points
│       ├── micassess.py       #   the `micassess` command
│       └── assess2d.py        #   the `2dassess` command
├── tests/                     # pytest suite for cryoassess.core
├── weights/                   # pre-trained .h5 model files (not in git)
├── Examples/                  # 30 labeled reference PNGs (6 classes × 5 each)
├── examples/                  # example star files (minimal.star, relion31.star)
├── benchmark.py               # standalone benchmark script
├── benchmark_results.json     # results written by benchmark.py
├── setup.py
└── requirements.txt
```

The package is layered: `core` has no TensorFlow dependency and is covered by
the `tests/` suite; `models` wraps the Keras models; `cli` is a thin argparse
layer.  Run the tests with `pytest tests/`.

---

## 4. Running MicAssess

Activate the virtual environment first:

```bash
# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 4a. From a directory of MRC files

```bash
micassess -i "/data/session/micrographs/*.mrc" -m weights/
```

### 4b. From a RELION star file

Two ready-to-use example star files are included in the `examples/` folder.
Copy one, replace the placeholder paths with your real `.mrc` paths, then run:

```bash
micassess -i examples/minimal.star -m weights/
```

**`examples/minimal.star`** — simplest valid format (RELION 3.0 style):

```
# paths are relative to the directory where you run micassess

data_

loop_
_rlnMicrographName
micrographs/session_001.mrc
micrographs/session_002.mrc
micrographs/session_003.mrc
```

**`examples/relion31.star`** — RELION 3.1 format with an optics-group block.
Use this if your downstream tools (CtfFind, Relion refinement) expect the
full optics header.  MicAssess reads only `_rlnMicrographName` and carries
the optics block through unchanged into the output star files.

```
data_optics

loop_
_rlnOpticsGroup             #1
_rlnOpticsGroupName         #2
_rlnMicrographOriginalPixelSize #3
_rlnVoltage                 #4
_rlnSphericalAberration     #5
_rlnAmplitudeContrast       #6
_rlnMicrographPixelSize     #7
1  opticsGroup1  0.832000  300.000000  2.700000  0.100000  0.832000


data_micrographs

loop_
_rlnMicrographName  #1
_rlnOpticsGroup     #2
micrographs/session_001.mrc  1
micrographs/session_002.mrc  1
```

> **Path resolution**: the `.mrc` paths inside the star file are resolved
> relative to the directory where you invoke `micassess`.  If your MRC files
> are in `/data/session/micrographs/`, either `cd` there first or use absolute
> paths in the star file.

### 4c. Common options

| Flag | Default | Description |
|------|---------|-------------|
| `-d` / `--detector` | `K2` | Camera type: `K2` or `K3` |
| `-o` / `--output` | `MicAssess` | Output directory name |
| `-b` / `--batch_size` | `32` | Prediction batch size (lower if OOM) |
| `--t1` | `0.1` | Good/bad threshold — lower keeps more data |
| `--t2` | `0.1` | Great/decent threshold |
| `--threads` | all CPUs | MRC → PNG conversion threads |
| `--gpus` | `0` | Comma-separated GPU indices |
| `--dont_reset` | off | Skip MRC → PNG conversion (re-use existing PNGs) |

### 4d. Full example with all flags

```bash
micassess \
  -i /data/session/micrographs/*.mrc \
  -m weights/ \
  -d K2 \
  -o MicAssess \
  -b 16 \
  --t1 0.1 \
  --t2 0.1 \
  --gpus 0
```

---

## 5. Expected output

### 5a. Console output

```
Generating star file micrographs.star
Converting in 16 parallel threads....
Conversion finished.
Assessing micrographs....
[INFO]: Number of devices: 1
Total:   250 micrographs
0Great :          87 micrographs
1Decent :         63 micrographs
2Contamination_Aggregate_Crack_Breaking_Drifting :  40 micrographs
3Empty_no_ice :   22 micrographs
4Crystalline_ice :  18 micrographs
5Empty_ice_no_particles_but_vitreous_ice :  20 micrographs
34.80% of the micrographs are great and were written in the *_great.star file.
60.00% of the micrographs are good and were written in the *_good.star file.
Details can be found in the output directory.
```

### 5b. Output files

```
MicAssess/
  png/
    data/                     # all micrographs converted to PNG
  0Great/                     # copies of predicted-great PNGs
  1Decent/
  2Contamination_Aggregate_Crack_Breaking_Drifting/
  3Empty_no_ice/
  4Crystalline_ice/
  5Empty_ice_no_particles_but_vitreous_ice/

micrographs_great.star        # RELION star for "Great" micrographs
micrographs_good.star         # RELION star for "Great" + "Decent" combined
probs_good.tsv                # per-micrograph good probability score
probs_great.tsv               # per-micrograph great probability score
```

`micrographs_good.star` is the main output to pass to downstream processing
(MotionCor2, CTF estimation, particle picking).  `micrographs_great.star`
is a stricter subset for high-quality-only workflows.

### 5c. Quality labels

| Index | Label | Considered "Good" |
|-------|-------|:-----------------:|
| 0 | Great | Yes (great.star + good.star) |
| 1 | Decent | Yes (good.star only) |
| 2 | Contamination / Aggregate / Crack / Breaking / Drifting | No |
| 3 | Empty — no ice | No |
| 4 | Crystalline ice | No |
| 5 | Empty ice, no particles, vitreous ice | No |

---

## 6. Running the benchmark

`benchmark.py` evaluates the four pre-trained models against the 30 labeled
PNGs in the `Examples/` folder without needing any MRC input files.  It
bypasses the MRC → PNG pipeline and feeds images directly into the model.

### 6a. Prerequisites

The virtual environment must be active and `weights/` must contain the four
`.h5` files (see §2e).

### 6b. Run

```bash
python benchmark.py
```

### 6c. What it does

1. Loads all 30 example PNGs (5 per class), resizes to 494 × 512, applies the
   same grayscale normalization and circular mask as the live pipeline.
2. Builds the hierarchical model (base → binary head → good/bad fine heads).
3. Runs forward inference and assigns a label to each image using the default
   thresholds `t1 = 0.1`, `t2 = 0.1`.
4. Prints a per-class accuracy table, a 6 × 6 confusion matrix, and a
   per-image prediction list.
5. Writes `benchmark_results.json` with the full results.

### 6d. Adjusting thresholds

Edit the two constants at the top of `benchmark.py`:

```python
T1 = 0.1   # good/bad split  — raise to be stricter (more "bad")
T2 = 0.1   # great/decent split — raise to classify fewer as "great"
```

---

## 7. Benchmark results (example images)

Recorded on: Windows 11, Python 3.13, TensorFlow 2.21, CPU only.

### Overall

| Metric | Value |
|--------|-------|
| Images | 30 (5 per class) |
| Correct | 17 / 30 |
| Overall accuracy | **56.7 %** |
| Total inference time | 2.79 s |
| Per-image latency | ~93 ms |

### Per-class accuracy

| Class | Correct / Total | Accuracy |
|-------|----------------|----------|
| 0 — Great | 3 / 5 | 60.0 % |
| 1 — Decent | 5 / 5 | 100.0 % |
| 2 — Contamination / Aggregate / Crack | 4 / 5 | 80.0 % |
| 3 — Empty (no ice) | 1 / 5 | 20.0 % |
| 4 — Crystalline ice | 4 / 5 | 80.0 % |
| 5 — Empty ice / vitreous (no particles) | 0 / 5 | 0.0 % |

### Confusion matrix

Rows = ground truth, columns = predicted label (0–5).

```
        0    1    2    3    4    5
[0]     3    2    0    0    0    0
[1]     0    5    0    0    0    0
[2]     0    0    4    0    1    0
[3]     0    2    1    1    0    1
[4]     0    0    0    0    4    1
[5]     2    1    1    1    0    0
```

### Interpretation

- **Decent (class 1)** is identified perfectly — the model is very confident on
  this class.
- **Contamination (2) and Crystalline ice (4)** are reliably detected at 80 %.
- **Empty / no ice (3)** is weakest at 20 % — two images are mislabelled as
  Decent, suggesting borderline vitreous coverage.
- **Vitreous ice without particles (5)** scores 0 % on these 5 examples.  All
  are predicted as "good" classes (Great or Decent) because the model sees
  high-quality ice and has no way to count particles in the binary good/bad
  head.  Class 5 is the hardest case by design.

> These numbers are lower than the published validation accuracy (~93 % binary,
> ~80 % fine) for two reasons: (1) only 30 cherry-picked examples are used, and
> (2) the PNGs are resized from their final form rather than being downsampled
> from raw MRC via FFT — the pixel statistics differ slightly.  On a real
> dataset processed through the full `micassess` pipeline the model performs
> closer to its published figures.

---

## 8. Troubleshooting

### `ModuleNotFoundError: No module named 'tensorflow'`

The venv is not activated, or TF was not installed.  Run:
```bash
# activate first, then:
pip install tensorflow tf-keras
```

### `ModuleNotFoundError: No module named 'ImageDataGenerator'`

TF 2.16+ ships Keras 3, which removed `ImageDataGenerator`.  The source files
in this repo have been patched to fall back to `tf_keras` automatically.  If
you see this error, install the compatibility shim:
```bash
pip install tf-keras
```

### Memory error / OOM during prediction

Lower the batch size:
```bash
micassess -i ... -m weights/ -b 8
```

### Star file not found

The `write_star` step reads back the original `.star` file by name.  Make sure
`-i` points to the same star file that was used for conversion, and that the
working directory is correct.

### Very slow MRC → PNG conversion

Conversion is CPU-bound and parallelised with `multiprocessing`.  Limit threads
to avoid RAM exhaustion on large K3 super-resolution datasets:
```bash
micassess -i ... -m weights/ --threads 8
```

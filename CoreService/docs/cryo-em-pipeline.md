# Cryo-EM pipeline tutorial — for the dev team

A walk-through of the full single-particle cryo-EM workflow, from a
microscope session to a published 3D structure. Aimed at developers
who haven't seen it before — explains *what* each step is, *why* it
matters, *which* RELION binary runs it, and *where* Magellon plugs in.

If you only know microscopy at the "it makes a picture of small
things" level, start here. If you've used RELION's GUI and just need
to know the CLI shape, skip to the [pipeline table](#the-pipeline-at-a-glance).

## Why this document exists

The cryo-EM workflow has ~12 distinct stages, each producing inputs
for the next. Some stages cost minutes, others cost a day on 8 GPUs.
Magellon orchestrates them as queue tasks; to plug a new tool in
correctly you need to know what each stage actually does to the
data. The vocabulary is dense (defocus astigmatism, gold-standard FSC,
Bayesian polishing) but the underlying ideas are not.

## The 30-second mental model

> A cryo-EM dataset is a few thousand to a few million 2D images of
> the same molecule frozen at random orientations. Each image is one
> projection of the 3D molecular density. The job of the pipeline is
> to figure out which orientation each image came from, then back-
> project all the images into one 3D density map.

Everything else is making that work in the presence of noise, motion,
imaging artefacts, and conformational heterogeneity.

## What a microscope session produces

A modern cryo-EM session on a 300 kV Krios with a Falcon 4i or K3
detector takes 12–48 hours and produces:

| Item | Typical size | What it is |
|---|---|---|
| **Movies** | 50–500 frames each, ~50 MB to several GB per micrograph | Each "image" is actually a movie — the detector records ~50 frames during one exposure so we can correct beam-induced motion. Stored as `.tif` (16-bit) or `.eer` (Falcon event format). |
| **Total micrographs per session** | 1k–10k | Each micrograph captures ~100–1000 particles. |
| **Pixel size** | 0.6–1.5 Å | Set by magnification × detector pixel size. |
| **Defocus range** | 0.5–3.0 µm | Deliberately spread to cover all spatial frequencies. |
| **Gain reference** | 1 file per session | Per-pixel sensitivity correction. |

Output: a **session directory** with raw movies, gain ref, and a
metadata STAR file that maps movies to acquisition parameters
(defocus, magnification, dose, etc.).

In Magellon: this is the data already on `/gpfs/<session>/rawdata/`.
The bus picks up new movies as they land.

## The pipeline at a glance

| # | Step | RELION binary | What it produces | Typical wall-clock | Magellon plugin |
|---|---|---|---|---|---|
| 1 | **Beam-induced motion correction** | `relion_run_motioncorr_mpi` (wraps MotionCor2/3) | Aligned, dose-weighted micrographs (`.mrc`) | 10–30 min for 1k movies on 4 GPUs | `magellon_motioncor_plugin` ✅ |
| 2 | **CTF estimation** | `relion_run_ctffind_mpi` (wraps CTFFIND4) | Per-micrograph defocus, astigmatism, CTF goodness | 5–10 min for 1k micrographs on 4 CPUs | `magellon_ctf_plugin` ✅ |
| 3 | **Particle picking** | `relion_autopick_mpi` (LoG / template / Topaz) | `.star` file of particle (x, y) coords per micrograph | 10–30 min | `magellon_topaz_plugin` ✅ |
| 4 | **Particle extraction** | `relion_preprocess_mpi --extract` | Particle stack (`.mrcs`) — boxes cut around each coord, normalised | 5–15 min | not yet — would be a thin plugin |
| 5 | **2D classification** | `relion_refine_mpi --K 50 ...` (no `--auto_refine`) | 50 representative 2D class averages + per-particle class assignment | 1–4 hours on 4 GPUs | not yet |
| 6 | **2D selection** | `relion_class_ranker` or manual | Cleaned `particles.star` (junk classes removed) | 5–15 min interactive | not yet |
| 7 | **Initial model** | `relion_refine_mpi --denovo_3dref` (VDAM) | A first 3D template (~10–20 Å resolution) | 30–60 min on 4 GPUs | not yet |
| 8 | **3D classification** | `relion_refine_mpi --K 4 --ref initial.mrc` | K separate 3D maps + per-particle class assignment | 4–24 hours | not yet |
| 9 | **3D refinement (gold-standard)** | `mpirun -np 3 relion_refine_mpi --auto_refine --split_random_halves` | Final 3D map + two half-maps (for FSC) | 4–24 hours | not yet |
| 10 | **CTF refinement** | `relion_ctf_refine_mpi` | Per-particle defocus + per-optics-group beam tilt + Zernike aberrations | 30–90 min | not yet |
| 11 | **Bayesian polishing** | `relion_motion_refine_mpi` | Per-particle motion correction using the 3D model as prior | 1–4 hours | not yet |
| 12 | **Refine again** | step 9 with the polished particles | Higher-resolution 3D map | 4–12 hours | not yet |
| 13 | **Postprocess** | `relion_postprocess` | Sharpened final map + FSC + resolution number | < 1 min | could fold into a plugin |
| 14 | **Local resolution** | `relion_postprocess --local_resolution` | Per-voxel resolution map | 5–15 min | not yet |
| 15 | **Atomic model building** | ModelAngelo (separate) | PDB / mmCIF | 1–6 hours | out of scope today |

A full "raw movies → publishable structure" pipeline is **typically 1–3 days** of compute on a multi-GPU workstation.

## Each step in detail

### 1. Motion correction

**Why**: each movie's frames suffer from beam-induced specimen motion
(specimen drifts ~5–50 Å during the exposure). If you sum the frames
naively you blur the image. Aligning the frames before summation
sharpens the resulting micrograph by ~2× resolution.

**What it does**: subdivides the frame into ~5×5 patches, finds
patch-wise translations between consecutive frames, fits a B-spline
to the translation field, sums dose-weighted aligned frames.

**Inputs**: movie stack + gain ref.
**Outputs**: one `.mrc` micrograph per movie + a `_PS.mrc` power-spectrum visualisation.
**Magellon today**: `magellon_motioncor_plugin` wraps MotionCor3 and is validated to 0.043 px mean error vs reference.

### 2. CTF estimation

**Why**: the microscope's lenses defocus the image to enhance contrast,
but defocus introduces a sinusoidal modulation in Fourier space (the
"Contrast Transfer Function") with spatial-frequency-dependent zeros
where signal is destroyed. To recover the signal, every later step
needs to know the CTF for each micrograph.

**What it does**: fits the CTF model `CTF(k) = sin(γ(k))` (where γ
encodes defocus, spherical aberration, voltage, amplitude contrast)
to the observed Thon rings in the micrograph's power spectrum.
Reports defocus_U, defocus_V, defocus_angle, and a goodness-of-fit.

**Inputs**: aligned micrograph.
**Outputs**: STAR row per micrograph with the CTF parameters + a diagnostic plot.
**Magellon today**: `magellon_ctf_plugin` wraps CTFFIND4 (4 backends inside the plugin: ctffind4_native reference, ctffind4_fast production, gctffind GPU, ctffind4_external).

### 3. Particle picking

**Why**: each micrograph contains 100–1000 particles in random
positions. We need to find them.

**What it does**: classical (Laplacian-of-Gaussian template
correlation, Class2D-template matching) or learned (Topaz CNN, crYOLO)
methods scan the micrograph for blob-like signals matching expected
particle size. Output: a list of (x, y) coordinates per micrograph.

**Inputs**: aligned micrograph + particle diameter (estimated from
the molecule).
**Outputs**: `coords.star` with one row per picked particle.
**Magellon today**: `magellon_topaz_plugin` provides Topaz-CNN picking; classical template-matching also exists in `magellon-rust-mrc/algorithms/particle_picker/`.

### 4. Particle extraction

**Why**: subsequent steps work on individual particle "boxes", not
whole micrographs. Cutting and normalising the boxes is its own step
because the box size and normalisation method affect resolution.

**What it does**: cuts a square region (e.g. 256×256 px) around each
coord. Normalises by subtracting the edge-ring mean and dividing by
the edge-ring stdev (the "white-edges" convention) — gives every
particle ~zero mean and unit noise stdev, which the E-M optimiser
expects. Optionally inverts contrast (cryo-EM is "dark protein on
bright background"; reconstruction expects the opposite).

**Inputs**: micrographs + coords + particle diameter.
**Outputs**: a single `.mrcs` stack (all particles concatenated) + a
`particles.star` with one row per particle and a pointer to its slice.
**Magellon today**: implemented in `magellon-rust-mrc/algorithms/spa/particle.rs`. Not yet wrapped as a CoreService plugin — would be ~1 day of work.

### 5. 2D classification — *why this matters more than it looks*

**Why**: picked particles include junk (ice contamination, broken
particles, neighbouring molecules incidentally cropped). 2D
classification clusters particles into K groups by appearance; bad
groups (blobs, ice, edge artefacts) are dropped, leaving a clean
particle set. Typical retention: 30–70% of picks.

**What it does**: Bayesian E-M with K independent 2D references.
Each particle is assigned a posterior over (class, in-plane angle,
shift). After convergence: each class average is the *de-noised*
sum of all particles assigned to it.

**Inputs**: `particles.star` (raw extracted boxes).
**Outputs**: `run_it025_classes.mrcs` (the K class averages) +
`run_it025_data.star` (per-particle class + pose posteriors).
**Magellon today**: not in shell-out path; partial in `magellon-rust-mrc` (CAN+MRA-based, not RELION's Bayesian approach).

### 6. 2D class selection

**Why**: 50 classes is more than a human can manually curate per
particle. RELION 5 has a CNN class-ranker that scores classes by
"likely-good vs likely-junk".

**What it does**: ResNet-18-class classifier outputs a score per class.
Above-threshold classes are kept.

**Inputs**: `run_it025_classes.mrcs`.
**Outputs**: `selected_particles.star` (subset of the input).
**Magellon today**: not exposed; could be wrapped as a Topaz-style ONNX plugin.

### 7. Initial model (3D template)

**Why**: 3D refinement needs a starting model. A bad starting model
gives a bad refinement (the optimisation is non-convex). For new
molecules without an existing PDB structure, we generate one from
the cleaned 2D particles using a stochastic gradient method (VDAM).

**What it does**: variational adaptive momentum gradient descent in
real space, randomly initialised. ~50 iterations. Converges to a
~10–20 Å low-resolution shape with the correct topology.

**Inputs**: cleaned 2D particles.
**Outputs**: a single low-res `.mrc` map.
**Magellon today**: not implemented anywhere.

### 8. 3D classification — heterogeneity removal

**Why**: even after 2D cleanup, particles may represent multiple
conformations of the molecule (open/closed, with/without ligand).
3D classification clusters particles by 3D shape so each conformation
gets its own reconstruction.

**What it does**: same Bayesian E-M as 2D classification but with K
*3D* references that are projected at every orientation per particle.

**Inputs**: 2D-cleaned particles + initial 3D model.
**Outputs**: K 3D maps + per-particle class assignment.
**Magellon today**: not in shell-out path.

### 9. 3D refinement (gold-standard) — the headline

**Why**: take the cleanest particle subset and refine it to highest
possible resolution. Gold-standard means we split the dataset into
two halves at the start and refine each *independently* — at the end
we compute FSC between the two reconstructions to get an unbiased
resolution estimate (without independent halves we'd be measuring
how well the same data agrees with itself, which is meaningless).

**What it does**: same Bayesian E-M but `--auto_refine` mode adapts
the angular sampling (HEALPix order) per iteration based on the
estimated angular accuracy. Refines until the FSC stops improving.
Runs in MPI: 1 master + 2 workers (one per half-set).

**Inputs**: cleaned particles (one or two STAR files for the two halves) + initial 3D model.
**Outputs**: `run_class001.mrc` (the final unmasked sum), `run_half1_class001_unfil.mrc` and `run_half2_class001_unfil.mrc` (the two unfiltered half-maps), full refined particle metadata.
**Magellon today**: not in shell-out path. The Rust port has every component (`magellon-rust-mrc/algorithms/spa/refinement/run_one_iteration`) but lacks the gold-standard wrapper (~2–4 weeks of work).

### 10. CTF refinement — getting the last 0.5 Å

**Why**: per-micrograph CTF estimation (step 2) is approximate.
After we have a high-resolution reference, we can re-estimate the
CTF *per particle* (defocus changes by ~50 nm across one micrograph)
and *per optics group* (beam tilt, magnification anisotropy, higher-
order Zernike aberrations). Tightens resolution by 0.2–0.5 Å.

**What it does**: holds the 3D map fixed, optimises CTF parameters
to maximise the per-particle log-likelihood.

**Inputs**: refined particles + refined map.
**Outputs**: particle STAR with corrected CTF columns.
**Magellon today**: not implemented.

### 11. Bayesian polishing — re-run motion correction with prior

**Why**: step 1 (motion correction) only knows about the micrograph's
own data. Once we have a high-res reference, we can re-do the per-frame
alignment using the model as a prior — for each particle, find the
frame-by-frame translations that maximise its likelihood under the
3D model. Tightens resolution by another 0.2–0.5 Å.

**What it does**: per-particle, per-frame alignment optimisation
with a smoothness prior across frames.

**Inputs**: refined particles + refined map + original movies.
**Outputs**: re-extracted particle STAR with polished motion.
**Magellon today**: not implemented; the standard 3D motion module
in `magellon-rust-mrc/algorithms/motion/` is the per-micrograph
version, not the per-particle-Bayesian one.

### 12. Refine again

After CTF refinement and polishing, re-run `Refine3D` with the
improved particles. Resolution improves further.

### 13. Postprocess — sharpening

**Why**: the refined map's high-frequency components are attenuated
by the imaging process (sample heterogeneity, residual motion). We
estimate the attenuation curve from a Guinier plot and apply the
inverse — "sharpening" — boosting high frequencies back up.

**What it does**:
1. Apply a soft-edge solvent mask to both half-maps to focus on the
   protein density.
2. Compute FSC between the two masked half-maps.
3. The FSC = 0.143 crossing gives the **resolution** number.
4. Fit `ln(power) ∝ -B·s²/2` in shells where signal dominates noise.
   The slope gives B (typical -50 to -200 Å²; negative is expected).
5. Apply `exp(+|B|·s²/4)` per Fourier shell, weight by the Heymann
   masked-FSC factor `√(2·FSC/(1+FSC))`, low-pass at the resolution
   cutoff.
6. Inverse FFT → final real-space sharpened map.

**Inputs**: two unfiltered half-maps + a solvent mask.
**Outputs**: sharpened final `.mrc` + FSC curve as ASCII + Guinier plot.
**Magellon today**: implemented in `magellon-rust-mrc/algorithms/spa/postprocess.rs` — works on real data; could replace `relion_postprocess` for plugin work *now* if we wire it into the bus.

### 14. Local resolution

**Why**: the global resolution number from FSC is a single value,
but real maps have *spatially varying* resolution — the molecule's
core might be at 2.0 Å while the flexible loops are at 4.0 Å. A local
resolution map shows this directly.

**What it does**: sliding-window FSC over local cubes of the volume.
**Magellon today**: not implemented; `magellon-rust-mrc/algorithms/spa/fsc.rs` does global FSC; local would extend it.

### 15. Atomic model building

The final 3D map is a density. To get a *protein structure* (PDB
file with atomic coordinates), you fit chains of amino acids into
the density. ModelAngelo (a transformer-based model) does this
automatically given the map + sequence; Coot is the manual-curation
tool. This step is downstream of everything in this doc.

## Where Magellon plugs into all of this

```
        ┌─────────────────┐
        │  microscope     │
        │  (movies, gain) │
        └────────┬────────┘
                 │ (filesystem watcher)
                 ▼
   ┌──────────────────────────────┐    Magellon orchestration
   │  CoreService task bus        │    (FastAPI, RabbitMQ tasks,
   │  ──────────────────────────  │     plugin containers)
   │  motioncor_tasks_queue       │
   │  ctf_tasks_queue             │
   │  particle_picking_q          │
   │  ...                         │
   │  (RELION jobs as new queues) │
   └──┬─────────┬─────────┬──────┬┘
      │         │         │      │
      ▼         ▼         ▼      ▼
   MotionCor  CTFFind  Topaz   (RELION-as-plugin)
   plugin     plugin   plugin   ← new

```

The architecture is already designed for this: `magellon_*_plugin/`
containers each consume one queue, do their thing, write outputs to
`/gpfs/jobs/<task-id>/`, post a result to the `*_out_tasks_queue`.
Adding RELION = new container + new queue, no platform changes.

## What Magellon-rust-mrc adds *beyond* what RELION provides

The native Rust port (`C:\projects\magellon-rust-mrc`) is at "everything
works for one E-M iteration". Its value over RELION-as-plugin:

1. **Sub-second latency** for "classify this one particle" (RELION's
   subprocess startup is 100–500 ms before any work).
2. **Streaming** — accumulate particles into the reconstruction *as
   they're picked*, no STAR-file marshalling between batches.
3. **In-process embedding** — the TUI viewer can compute Class2D in
   the same process; web/WASM/mobile too.
4. **CI-friendly** — no GPU + CUDA + drivers needed for tests.
5. **Multi-GPU-vendor** — cubecl targets CUDA + HIP (AMD) + SYCL
   (Intel) from one codebase.

For most production use the Rust port is **not on the critical path**:
shell out RELION for everything that runs once-per-dataset, and
reserve the Rust port for the interactive / streaming / embedded
features that are Magellon-distinct.

See [`magellon-rust-mrc/docs/relion-port-status.md`](../../magellon-rust-mrc/docs/relion-port-status.md)
for what's implemented in Rust and what's still RELION-only.

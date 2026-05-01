# test-6-relion postmortem — what worked, what bit us

A concrete log of the May 2026 RELION 5 test drive on AWS. If you're
re-running this or shipping it to production, read this before
following the README.

## TL;DR

| | |
|---|---|
| **Account** | 789438509093 (FSU SSO) |
| **Region** | us-east-1 |
| **Instance** | `g5.2xlarge` on-demand (1× A10G 24 GB, 8 vCPU, 32 GB RAM, 80 GB gp3 root) |
| **AMI** | Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.4 (Ubuntu 22.04) — `ami-0aee7b90d684e107d` at the time |
| **Total wall-clock** | ~30 min (including ~7 min RELION compile) |
| **Total cost** | < $1 (~$0.50 instance + ~$0.10 data egress) |
| **Final resolution** | 2.46 Å (β-galactosidase, post-sharpened, gold-standard FSC) |

## Timeline of what worked

1. **Refresh SSO creds** → `source common/activate.sh` reads `.env`.
   `aws sts get-caller-identity` confirms the role.
2. **`./00-launch.sh`** — runs the launch script. Took ~7 min total.
   - Picks the latest "Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.4 (Ubuntu 22.04)" (saves us installing CUDA + drivers).
   - Creates SG `magellon-gpu-eval-relion-sg` with port 22 open from the caller's public IP only.
   - Creates key pair `magellon-gpu-eval-relion-key` at `~/.ssh/`.
   - Runs `ec2 run-instances` on `g5.2xlarge` on-demand.
   - User-data: `apt install` build deps (~1.5 min), `git clone` RELION 5.0 (~30 s), `cmake -DCUDA=ON -DCUDA_ARCH=86`, `make -j8 install` (~5 min on 8 vCPU).
   - Verified install: `/opt/relion/bin/relion_refine --version` →
     `RELION version: 5.0.1-commit-cad71b ; Precision: BASE=double, CUDA-ACC=single`.
3. **`./01-fetch-data.sh`** — wgets the tutorial data + precalculated
   results (~3 GB total) from `ftp://ftp.mrc-lmb.cam.ac.uk/pub/scheres/`.
   Takes ~2 min on AWS bandwidth. Extracts to `/data/Tutorial5.0/`.
4. **`./02-class2d.sh`** — Class2D with K=25, 5 iterations, 9k particles.
   ~3 min. Outputs `/work/Class2D/run_it005_classes.mrcs` (the 25 class averages).
5. **`./03-class3d.sh`** — Class3D K=4, 5 iterations, using the precomputed
   InitialModel as reference. ~3 min. Outputs 4× `run_it005_class00*.mrc`.
6. **`./04-refine3d.sh`** — Refine3D `--auto_refine --split_random_halves`
   via `mpirun -np 3 relion_refine_mpi`. Auto-converged at iter ~22.
   ~5 min wall-clock. Outputs `run_class001.mrc` + the two `run_half*_class001_unfil.mrc`.
7. **`./05-postprocess.sh`** — MaskCreate (~10 s) + PostProcess (~10 s).
   Reports **FINAL RESOLUTION 2.46 Å**.
8. **`./06-fetch-results.sh`** — bundles outputs into a tarball on the
   instance, scps it back, extracts to `outputs/results-bundle/`.
   ~12 MB total. ~30 s.
9. **`./99-teardown.sh`** — `terminate-instances` + delete SG + delete
   key pair + remove `.pem`. ~30 s.

## What bit us — fix once, document forever

### 1. `set -a` in `common/activate.sh` clobbers `SCRIPT_DIR`

`common/activate.sh` has `set -a` before sourcing config. `config.sh`
declares its own `SCRIPT_DIR` which then leaks back into the caller's
shell, *replacing* the script's own `SCRIPT_DIR`. Subsequent `source
"${SCRIPT_DIR}/.instance-env"` lines fail with "no such file" because
`SCRIPT_DIR` now points at `common/`, not `test-6-relion/`.

**Fix** (now in every script): save and restore.
```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
```

`test-5-gpu-node-e2e/00-launch.sh` already had this pattern. We
replicated it everywhere.

### 2. `relion_refine` (non-MPI) refuses `--split_random_halves`

Naïvely running:
```bash
relion_refine --auto_refine --split_random_halves ...
```
fails immediately with:
```
ERROR: Cannot split data into random halves without using MPI!
For debugging ONLY, use --debug_split_random_half 1 (or 2)
```

Auto-refine *requires* MPI for the gold-standard split. Even on a
single-GPU box, you need:
```bash
mpirun --allow-run-as-root -np 3 \
  /opt/relion/bin/relion_refine_mpi \
  --auto_refine --split_random_halves \
  --gpu "0:0" ...
```

`-np 3` = 1 master + 2 workers (one per half). The `--gpu "0:0"`
syntax assigns GPU 0 to both halves (they share since we only have
one device). Use `--gpu "0:1"` on a multi-GPU box.

The `--allow-run-as-root` flag is harmless — RELION's container path
runs as root by default. Drop it if you `useradd` an unprivileged
account first.

### 3. `relion_postprocess --i` wants a half-map *file*, not a directory

The RELION GUI hides this. The CLI is picky: it sniffs the input
filename for `half1` or `half2` and refuses to proceed without one.

Wrong:
```bash
relion_postprocess --i Refine3D/run --o ...    # ERROR
```

Right:
```bash
relion_postprocess --i Refine3D/run_half1_class001_unfil.mrc --o ...
```

It auto-finds `run_half2_..._unfil.mrc` from the `half1` filename.

### 4. `gs` (ghostscript) missing — empty PDF logs, harmless

```
sh: 1: gs: not found
ERROR in executing: gs ...
+ Will make an empty PDF-file in PostProcess/logfile.pdf
```

PostProcess emits a PDF summary by piping its EPS plots through
ghostscript. The DLAMI doesn't have `gs` installed. The numerical
outputs (postprocess.mrc, postprocess.star, postprocess_fsc.dat) all
write fine — only the visual summary PDF is missing. Add
`apt install ghostscript` to the user-data if you want the PDF.

### 5. `--split_random_halves` requires per-half launch directories

Our 04-refine3d.sh starts with `rm -rf /work/Refine3D` because the
first attempt (without MPI) created a partial output that confused
the second attempt. Always start auto-refine from an empty output
directory.

### 6. AWS SCP gotchas (not our scripts; account-level)

- `ec2:DescribeInstances` is allowed, but our SSO role has an
  org-level **Service Control Policy** that denies certain operations
  in some regions. We saw this transiently when running
  `aws ec2 describe-instances` — same identity, same instance-ids,
  but `UnauthorizedOperation` from the SCP. The launch + run + scp
  paths weren't affected.
- `us-east-2` is blocked by the FSU org SCP entirely. Stay in
  `us-east-1`.

## Cost breakdown

| Item | Charge |
|---|---|
| `g5.2xlarge` on-demand × 30 min | $0.61 |
| 80 GB gp3 EBS × 30 min | < $0.01 |
| Data egress (results scp ~12 MB) | < $0.001 |
| **Total** | **~$0.62** |

Spot would have been ~$0.20 but Refine3D's runtime makes spot
interruption a real risk. The $0.40 difference isn't worth it for a
one-off; revisit if we run this nightly.

The $50/month sandbox budget alarm fired no warnings. Plenty of
runway for repeated runs and longer datasets.

## What this proves and what it doesn't

**Proven:**
- RELION 5 builds from source on the standard DLAMI in ~5 min on a
  g5.2xlarge.
- The full canonical pipeline (Class2D → Class3D → Refine3D → PostProcess)
  runs end-to-end against the official tutorial dataset with no manual
  intervention beyond running the seven shell scripts.
- The same scripts encode the two non-obvious gotchas (MPI for
  auto-refine; explicit half1 filename for postprocess) so future runs
  don't re-discover them.
- Total cost (~$0.62) and wall-clock (~30 min) are inside the
  per-iteration budget for a CI smoke test.

**Not proven (out of scope for this test drive):**
- CtfRefine + Polish — these need movies + per-particle CTF, which
  the tutorial-precalc bundle has but we didn't exercise. Add scripts
  if there's a use case.
- Gold-standard convergence on a *real* dataset (this was a 9k-particle
  toy). Resolution numbers from this run aren't a benchmark, just a
  health check.
- ResMap / local-resolution. RELION 5 has it built-in
  (`relion_postprocess --local_resolution`); we didn't run it.
- Multi-GPU scaling. We have one A10G; for an 8-GPU `p4d` test, the
  `--gpu` argument changes to `"0:1:2:3:4:5:6:7"` and `mpirun -np 9`.

## Re-running

```bash
cd C:/projects/Magellon/CoreService/sandbox/aws/test-6-relion
# Refresh SSO creds in ../.env first.
bash 00-launch.sh         # ~7 min
bash 01-fetch-data.sh     # ~2 min
bash 02-class2d.sh        # ~3 min
bash 03-class3d.sh        # ~3 min
bash 04-refine3d.sh       # ~5 min
bash 05-postprocess.sh    # < 1 min
bash 06-fetch-results.sh  # < 1 min
bash 99-teardown.sh       # < 1 min
```

Total ~30 min unattended (each step blocks until done). For
hands-off CI, chain them with `&&` and add a `set -e` guard at the
top of an outer wrapper.

## Outputs left in `outputs/results-bundle/`

```
Class2D/
  run_it005_classes.mrcs         (25 2D class averages, 410 KB)
  run_it005_model.star           (per-class metadata)
  run.out                        (full RELION stdout)
Class3D/
  run_it005_class00{1..4}.mrc    (4× 3D classes)
  run_it005_model.star
  run.out
Refine3D/
  run_class001.mrc               (final reconstruction)
  run_half{1,2}_class001_unfil.mrc  (the gold-standard half-maps)
  run_model.star
  run.out
MaskCreate/
  mask.mrc                       (solvent mask)
PostProcess/
  postprocess.mrc                (FINAL sharpened map @ 2.46 Å)
  postprocess_masked.mrc         (mask-applied final)
  postprocess_fsc.dat            (FSC vs frequency, ASCII)
  postprocess_fsc.eps            (FSC plot)
  postprocess_guinier.eps        (Guinier B-factor fit plot)
  postprocess.star               (metadata)
  run.out
```

These are also useful as **golden oracles for the Rust port** —
see `../../../magellon-rust-mrc/docs/relion-port-status.md`.

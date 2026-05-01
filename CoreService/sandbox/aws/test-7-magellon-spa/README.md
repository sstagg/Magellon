# test-7-magellon-spa — same pipeline as test-6, our Rust port instead of RELION

End-to-end Class2D → Class3D → Refine3D → CtfRefine on the official
β-galactosidase tutorial dataset, using **`magellon-spa`** (the Rust port
at `magellon-rust-mrc`) instead of `relion_refine`.

## Why this exists

`test-6-relion/` runs RELION 5 to produce the ground-truth pipeline
outputs we use as oracles for the Rust port (commit `c9d6cb5` on
`magellon-rust-mrc`). `test-7-magellon-spa/` is the symmetric partner:
**run our port on the same dataset, same particles, same configs**, then
compare its outputs against test-6's RELION outputs. The diff tells us
where the port still drifts from RELION.

## Layout

```
00-launch.sh            ec2 run-instances + install Rust toolchain
01-fetch-data.sh        wget + extract the tutorial dataset (same as test-6)
02-build-magellon.sh    git clone + cargo build --release --features spa
03-class2d.sh           magellon-spa class2d --K 25 --iters 5
04-class3d.sh           magellon-spa class3d --K 4 --iters 5 --reference InitialModel.mrc
05-refine3d.sh          magellon-spa refine3d
06-ctf-refine.sh        magellon-spa ctf-refine          ← new in test-7 (test-6 didn't exercise this)
07-fetch-results.sh     scp outputs back to outputs/
99-teardown.sh          terminate + delete sg + key

10-run-full-pipeline.sh resilient driver — waits for build, runs 03-07 + teardown
```

## Instance choice

`c5.4xlarge` (16 vCPU, 32 GB RAM, ~$0.68/hr). Our Rust SPA path is
**CPU-only** — no CUDA backend wired through to `class2d` / `class3d` /
`refine3d` yet (that's a future Phase K extension). c5.4xlarge gives
double the CPU vs test-6's g5.2xlarge for similar cost; we're CPU-bound,
not GPU-bound.

Total wall-clock estimate: ~25 min (no RELION compile to wait on; Rust
release build is ~3 min). Cost ~$0.30.

## How to run

```bash
cd C:/projects/Magellon/CoreService/sandbox/aws/test-7-magellon-spa
# Refresh SSO creds in ../.env first (same .env as test-6).
bash 00-launch.sh                  # ~3 min — instance up + Rust toolchain
bash 01-fetch-data.sh              # ~2 min — tutorial dataset
bash 02-build-magellon.sh          # ~5 min — cargo build --release --features spa
bash 10-run-full-pipeline.sh       # ~15 min — Class2D + Class3D + Refine3D + CtfRefine + fetch + teardown
```

## What this proves once it lands

- Rust port can run end-to-end on real cryo-EM data, not just the
  synthetic / oracle tests we have today.
- Same dataset → side-by-side comparison with test-6's RELION outputs.
- Specifically validates I.2 / I.2b / I.2c (CtfRefine) which test-6
  didn't exercise (RELION has its own ctf_refine, we'd need to add a
  step to test-6 for true parity — that's `08-ctf-refine.sh` queued
  on the test-6 side).

## What it does *not* prove

- GPU performance — magellon-spa CPU-only for now. Phase K can add a
  CUDA backend when the algorithmic surface stabilises.
- Resolution parity at single-Å accuracy — Class2D / Class3D oracle
  correlations against RELION are 0.5–0.95 today (per `tests/spa_*_oracle.rs`),
  not 1.0. test-7's outputs vs test-6's outputs will reflect that gap.

## Cross-comparison helper

After both test-6 and test-7 outputs are fetched locally (under
`outputs/results-bundle/`), the existing oracle tests at
`magellon-rust-mrc/tests/spa_*_oracle.rs` compare specific field-by-field
numerical outputs. test-7's `outputs/` will be the new oracle target —
update `sandbox/relion-oracle/data/` with both RELION-side (test-6) and
magellon-side (test-7) data after a side-by-side run.

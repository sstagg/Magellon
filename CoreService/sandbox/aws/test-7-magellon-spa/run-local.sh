#!/usr/bin/env bash
# Run magellon-spa locally against the input particles already on disk
# at magellon-rust-mrc/sandbox/relion-oracle/data/inputs/. Saves wall-
# clock timing per stage. Same pipeline as the AWS scripts but skips
# launch / instance / scp / teardown — for CPU-only workloads, local
# is strictly cheaper + faster.
#
# Prerequisites:
#   1. cargo build --release --features spa --bin magellon-spa
#   2. The 8 input particle stacks at
#      magellon-rust-mrc/sandbox/relion-oracle/data/inputs/

set -euo pipefail

LOCAL_REPO="${LOCAL_REPO:-C:/projects/magellon-rust-mrc}"
INPUTS="${LOCAL_REPO}/sandbox/relion-oracle/data/inputs"
OUTPUTS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)/outputs-local"
BIN="${LOCAL_REPO}/target/release/magellon-spa"

[ -x "$BIN" ] || { echo "ERROR: $BIN not built. Run: cargo build --release --features spa --bin magellon-spa" >&2; exit 1; }
[ -d "$INPUTS" ] || { echo "ERROR: $INPUTS missing" >&2; exit 1; }

mkdir -p "$OUTPUTS"/{Class2D,Class3D,Refine3D,CtfRefine}

# Helper: run a stage with timestamping. Windows git-bash doesn't have
# /usr/bin/time; fall back to bash's `time` builtin written to file
# via process substitution.
run_stage() {
  local name=$1
  shift
  local outdir="$OUTPUTS/$name"
  echo
  echo "=== $name ==="
  local start_s
  start_s=$(date +%s)
  "$@" 2>&1 | tee "$outdir/run.out" | tail -20
  local end_s
  end_s=$(date +%s)
  local elapsed=$((end_s - start_s))
  echo "$name: ${elapsed} s wall-clock" | tee -a "$outdir/timing.txt"
}

PARTICLES="$INPUTS/particles.star"
STACKS_ROOT="$INPUTS/particle_stacks"
INITIAL_MODEL="$INPUTS/initial_model.mrc"

run_stage Class2D "$BIN" class2d \
  --particles "$PARTICLES" \
  --particle-stacks-root "$STACKS_ROOT" \
  --output-dir "$OUTPUTS/Class2D" \
  -K 25 --iters 5

run_stage Class3D "$BIN" class3d \
  --particles "$PARTICLES" \
  --particle-stacks-root "$STACKS_ROOT" \
  --reference "$INITIAL_MODEL" \
  --output-dir "$OUTPUTS/Class3D" \
  -K 4 --iters 5

run_stage Refine3D "$BIN" refine3d \
  --particles "$PARTICLES" \
  --particle-stacks-root "$STACKS_ROOT" \
  --reference "$INITIAL_MODEL" \
  --pixel-size 3.54 \
  --output-dir "$OUTPUTS/Refine3D" \
  --max-iters 5

# CtfRefine needs a refined map; prefer Refine3D's output, fall back to InitialModel.
MAP="$OUTPUTS/Refine3D/final.mrc"
[ -f "$MAP" ] || MAP="$INITIAL_MODEL"

run_stage CtfRefine "$BIN" ctf-refine \
  --particles "$PARTICLES" \
  --particle-stacks-root "$STACKS_ROOT" \
  --map "$MAP" \
  --output-dir "$OUTPUTS/CtfRefine"

echo
echo "=== complete ==="
echo "Local outputs: $OUTPUTS"
echo "RELION reference: $LOCAL_REPO/sandbox/relion-oracle/data/pipeline/"
echo
echo "Per-stage wall-clock:"
grep -h "wall-clock" "$OUTPUTS"/*/timing.txt

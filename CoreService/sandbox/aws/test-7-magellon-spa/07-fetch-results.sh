#!/usr/bin/env bash
# Pull the magellon-spa pipeline outputs back to outputs/.
# Also bundles the input particle subset used by the run, so the
# magellon-rust-mrc oracle tests can compare these directly to
# test-6's RELION outputs.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

OUT="${SCRIPT_DIR}/outputs"
mkdir -p "$OUT"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'STAGE'
set -euxo pipefail
mkdir -p /tmp/results-bundle/{Class2D,Class3D,Refine3D,CtfRefine,Inputs}

# Class2D — single .mrcs of K class averages + model.star.
[ -d /work/Class2D ] && cp /work/Class2D/* /tmp/results-bundle/Class2D/ 2>/dev/null || true

# Class3D — K .mrc files + model.star.
[ -d /work/Class3D ] && cp /work/Class3D/* /tmp/results-bundle/Class3D/ 2>/dev/null || true

# Refine3D — final.mrc + half-maps + fsc.dat.
[ -d /work/Refine3D ] && cp /work/Refine3D/* /tmp/results-bundle/Refine3D/ 2>/dev/null || true

# CtfRefine — refined_particles.star.
[ -d /work/CtfRefine ] && cp /work/CtfRefine/* /tmp/results-bundle/CtfRefine/ 2>/dev/null || true

# Input particles + initial model (small subset — first 8 .mrcs files,
# ~100 particles each, enough for any per-particle oracle to re-run
# locally). Same convention as test-6's 06-fetch.
INPUT_PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
INITIAL_MODEL=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
[ -f "$INITIAL_MODEL" ] || INITIAL_MODEL=/data/Tutorial5.0/InitialModel/job015/run_it020_class001.mrc

[ -f "$INPUT_PARTICLES" ] && cp "$INPUT_PARTICLES" /tmp/results-bundle/Inputs/particles.star
[ -f "$INITIAL_MODEL" ] && cp "$INITIAL_MODEL" /tmp/results-bundle/Inputs/initial_model.mrc

mkdir -p /tmp/results-bundle/Inputs/particle_stacks/Extract/job012/Movies
ls /data/Tutorial5.0/Extract/job012/Movies/*.mrcs 2>/dev/null \
  | head -8 \
  | xargs -I {} cp {} /tmp/results-bundle/Inputs/particle_stacks/Extract/job012/Movies/ 2>/dev/null || true

# Provenance: which commit of magellon-rust-mrc produced these outputs?
{
  echo "=== magellon-rust-mrc HEAD ==="
  git -C /src/magellon-rust-mrc log -1 --oneline 2>/dev/null || echo "unknown"
  echo
  echo "=== magellon-spa --help ==="
  magellon-spa --help 2>&1 | head -30 || true
  echo
  echo "=== build host ==="
  uname -a
} > /tmp/results-bundle/PROVENANCE.txt

du -sh /tmp/results-bundle/ 2>/dev/null
cd /tmp && tar -czf magellon-spa-bundle.tar.gz results-bundle/
ls -la /tmp/magellon-spa-bundle.tar.gz
STAGE

scp -o StrictHostKeyChecking=no -i "$KEY_FILE" \
  ubuntu@"$PUBLIC_IP":/tmp/magellon-spa-bundle.tar.gz "$OUT/"
cd "$OUT" && tar -xzf magellon-spa-bundle.tar.gz && rm magellon-spa-bundle.tar.gz

echo
echo "=== fetched ==="
{ find "$OUT" -type f 2>/dev/null || true; } | sort | head -40 || true
echo
echo "Tear down with: ./99-teardown.sh"

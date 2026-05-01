#!/usr/bin/env bash
# Class3D K=4, 5 iters. Uses the precomputed VDAM InitialModel from
# the tutorial as the starting reference (matches test-6 exactly).
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
REF=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
[ -f "$REF" ] || REF=/data/Tutorial5.0/InitialModel/job015/run_it020_class001.mrc
[ -f "$PARTICLES" ] || { echo "missing $PARTICLES"; exit 1; }
[ -f "$REF" ] || { echo "no initial model"; exit 1; }
echo "Reference: $REF"

mkdir -p /work/Class3D
cd /data/Tutorial5.0

echo "=== magellon-spa class3d ==="
time magellon-spa class3d \
  --particles "$PARTICLES" \
  --particle-stacks-root /data/Tutorial5.0 \
  --reference "$REF" \
  --output-dir /work/Class3D \
  -K 4 \
  --iters 5 \
  2>&1 | tee /work/Class3D/run.out | tail -40

echo
echo "=== outputs in /work/Class3D ==="
ls -la /work/Class3D/ 2>/dev/null | head -10
REMOTE

echo
echo "Class3D complete. Next: ./05-refine3d.sh"

#!/usr/bin/env bash
# Class2D — K=25, 5 iters. Same parameters as test-6's RELION run so
# the two pipelines are head-to-head comparable.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
[ -f "$PARTICLES" ] || { echo "missing $PARTICLES"; exit 1; }

mkdir -p /work/Class2D
# Run from /data/Tutorial5.0 so relative `_rlnImageName` paths resolve.
cd /data/Tutorial5.0

# magellon-spa class2d:
#   --particles particles.star
#   --particle-stacks-root  (where the .mrcs files live, relative to STAR)
#   --output-dir
#   -K 25 --iters 5
# Box size auto-detected from the first particle stack.
echo "=== magellon-spa class2d ==="
time magellon-spa class2d \
  --particles "$PARTICLES" \
  --particle-stacks-root /data/Tutorial5.0 \
  --output-dir /work/Class2D \
  -K 25 \
  --iters 5 \
  2>&1 | tee /work/Class2D/run.out | tail -40

echo
echo "=== outputs in /work/Class2D ==="
ls -la /work/Class2D/ 2>/dev/null | head -10
REMOTE

echo
echo "Class2D complete. Next: ./04-class3d.sh"

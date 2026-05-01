#!/usr/bin/env bash
# Refine3D — auto-refine outer loop with split halves. Uses our just-
# completed Class3D best class as the seed reference; falls back to the
# tutorial's InitialModel.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
# Prefer the cleaner post-Class2D-selection particles for Refine3D.
PARTICLES=/data/Tutorial5.0/Select/job017/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Select/job014/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star

REF=""
if [ -f /work/Class3D/class001.mrc ]; then
  REF=/work/Class3D/class001.mrc
else
  REF=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
fi
echo "Particles: $PARTICLES"
echo "Reference: $REF"

mkdir -p /work/Refine3D
cd /data/Tutorial5.0

# Pixel size from the tutorial dataset header (3.54 Å/px on the
# downsampled extracted particles).
echo "=== magellon-spa refine3d (release mode, performance-instrumented) ==="
/usr/bin/time -v -o /work/Refine3D/timing.txt \
  magellon-spa refine3d \
    --particles "$PARTICLES" \
    --particle-stacks-root /data/Tutorial5.0 \
    --reference "$REF" \
    --pixel-size 3.54 \
    --output-dir /work/Refine3D \
    --max-iters 10 \
  2>&1 | tee /work/Refine3D/run.out | tail -50
echo
echo "=== Refine3D performance ==="
cat /work/Refine3D/timing.txt

echo
echo "=== Refine3D outputs ==="
ls -la /work/Refine3D/ 2>/dev/null | head -10
echo
echo "=== reported resolution (if any) ==="
grep -E "(resolution|FSC=0.143)" /work/Refine3D/run.out | tail -10 || true
REMOTE

echo
echo "Refine3D complete. Next: ./06-ctf-refine.sh"

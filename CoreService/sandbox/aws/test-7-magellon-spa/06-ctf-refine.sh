#!/usr/bin/env bash
# CtfRefine — per-particle defocus + astigmatism angle refinement
# against the just-refined map. test-6's RELION run didn't exercise
# this; test-7 is where it lands.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
PARTICLES=/data/Tutorial5.0/Select/job017/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Select/job014/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star

# Prefer Refine3D's averaged final map; fall back to Class3D best class.
MAP=""
if [ -f /work/Refine3D/final.mrc ]; then
  MAP=/work/Refine3D/final.mrc
elif [ -f /work/Class3D/class001.mrc ]; then
  MAP=/work/Class3D/class001.mrc
else
  MAP=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
fi
echo "Particles: $PARTICLES"
echo "Reference map: $MAP"

mkdir -p /work/CtfRefine
cd /data/Tutorial5.0

echo "=== magellon-spa ctf-refine (release mode, performance-instrumented) ==="
/usr/bin/time -v -o /work/CtfRefine/timing.txt \
  magellon-spa ctf-refine \
    --particles "$PARTICLES" \
    --particle-stacks-root /data/Tutorial5.0 \
    --map "$MAP" \
    --output-dir /work/CtfRefine \
  2>&1 | tee /work/CtfRefine/run.out | tail -40
echo
echo "=== CtfRefine performance ==="
cat /work/CtfRefine/timing.txt

echo
echo "=== CtfRefine outputs ==="
ls -la /work/CtfRefine/ 2>/dev/null | head -5
echo
echo "=== refined particle defocus columns (head) ==="
[ -f /work/CtfRefine/refined_particles.star ] && \
  head -40 /work/CtfRefine/refined_particles.star || \
  echo "(no refined_particles.star yet)"
REMOTE

echo
echo "CtfRefine complete. Next: ./07-fetch-results.sh"

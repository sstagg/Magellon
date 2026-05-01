#!/usr/bin/env bash
# Class3D — K=4 classes, 5 iterations, ~20 min.
# Needs an initial reference. RELION 5 tutorial ships one; if not, we
# generate it via InitialModel first (VDAM, ~5 extra min).
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
cd /data/Tutorial5.0

PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
[ -f "$PARTICLES" ] || { echo "missing $PARTICLES"; exit 1; }

# Use the precomputed InitialModel from the tutorial — its iter 90 is the
# converged VDAM result.
REF=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
[ -f "$REF" ] || REF=/data/Tutorial5.0/InitialModel/job015/run_it020_class001.mrc
[ -f "$REF" ] || { echo "no initial model"; ls /data/Tutorial5.0/InitialModel/job015/ | head; exit 1; }
echo "Reference: $REF"

mkdir -p /work/Class3D
/opt/relion/bin/relion_refine \
  --i "$PARTICLES" \
  --o /work/Class3D/run \
  --ref "$REF" \
  --K 4 \
  --iter 5 \
  --tau2_fudge 4 \
  --particle_diameter 200 \
  --healpix_order 1 \
  --offset_range 5 --offset_step 2 \
  --pool 30 --pad 2 \
  --norm --scale --firstiter_cc \
  --gpu 0 --j 4 \
  2>&1 | tee /work/Class3D/run.out | tail -80

echo
echo "=== outputs in /work/Class3D ==="
ls -la /work/Class3D/run_it005_class00*.mrc 2>/dev/null | head -10
REMOTE

echo
echo "Class3D complete. Next: ./04-refine3d.sh"

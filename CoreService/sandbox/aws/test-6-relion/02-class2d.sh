#!/usr/bin/env bash
# Class2D — 25 classes, 5 iterations. ~10 min on g5.2xlarge.
# Smallest E-M test that exercises the full RELION refinement engine.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail

# Tutorial dataset is laid out as /data/Tutorial5.0/<JobName>/jobNNN/.
# Use the clean "Select" output (post-Class2D selection) for a well-
# behaved test — fewer junk particles → cleaner classes faster.
PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
[ -f "$PARTICLES" ] || { echo "missing $PARTICLES"; find /data/Tutorial5.0 -name "particles.star" | head; exit 1; }
echo "Using particles: $PARTICLES"

# RELION needs to find micrograph paths relative to its working directory
# (the STAR rows look like "MotionCorr/job002/Movies/...mrc"). Run from
# /data/Tutorial5.0 so those relative paths resolve.
mkdir -p /work/Class2D
cd /data/Tutorial5.0

# Class2D parameters — kept small for the test drive:
# K=25 classes, 5 iterations, healpix order 1 (small in-plane search).
# tau2_fudge=2 is RELION's default, particle_diameter ~200 Å covers
# β-galactosidase (~13 nm).
/opt/relion/bin/relion_refine \
  --i "$PARTICLES" \
  --o /work/Class2D/run \
  --K 25 \
  --iter 5 \
  --tau2_fudge 2 \
  --particle_diameter 200 \
  --pool 30 \
  --pad 2 \
  --healpix_order 1 \
  --offset_range 5 --offset_step 2 \
  --norm --scale \
  --gpu 0 \
  --j 4 \
  2>&1 | tee /work/Class2D/run.out | tail -80

echo
echo "=== outputs in /work/Class2D ==="
ls -la /work/Class2D/run_it005_* 2>/dev/null | head -10
REMOTE

echo
echo "Class2D complete. Next: ./03-class3d.sh (or fetch the classes preview now via 06-fetch-results.sh)"

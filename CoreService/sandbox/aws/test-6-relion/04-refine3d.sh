#!/usr/bin/env bash
# Refine3D --auto_refine --split_random_halves — the headline gold-standard
# reconstruction. ~45 min on g5.2xlarge with the small tutorial dataset.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
cd /data/Tutorial5.0

# Use the cleanest "Select" output (post-Class2D-selection) for Refine3D.
PARTICLES=/data/Tutorial5.0/Select/job017/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Select/job014/particles.star
[ -f "$PARTICLES" ] || PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
[ -f "$PARTICLES" ] || { echo "no particles"; exit 1; }
echo "Particles: $PARTICLES"

# Reference: prefer our just-completed Class3D best class; fall back to
# the precomputed InitialModel.
REF=""
if [ -f /work/Class3D/run_it005_class001.mrc ]; then
  REF=/work/Class3D/run_it005_class001.mrc
else
  REF=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
fi
echo "Reference: $REF"

rm -rf /work/Refine3D
mkdir -p /work/Refine3D

# RELION's --split_random_halves requires MPI: 1 master + 2 workers, one
# per half-set. All share GPU 0 (g5.2xlarge has only one GPU).
mpirun --allow-run-as-root -np 3 \
  /opt/relion/bin/relion_refine_mpi \
  --i "$PARTICLES" \
  --o /work/Refine3D/run \
  --ref "$REF" \
  --auto_refine --split_random_halves \
  --ini_high 50 \
  --tau2_fudge 4 \
  --particle_diameter 200 \
  --healpix_order 2 --auto_local_healpix_order 4 \
  --offset_range 5 --offset_step 2 \
  --pool 30 --pad 2 \
  --norm --scale --firstiter_cc \
  --low_resol_join_halves 40 \
  --gpu "0:0" --j 4 \
  2>&1 | tee /work/Refine3D/run.out | tail -100

echo
echo "=== Refine3D outputs ==="
ls -la /work/Refine3D/run_class001.mrc /work/Refine3D/run_half*_class001.mrc 2>/dev/null
echo
echo "=== reported resolution ==="
grep -E "(final|resolution|Auto-refine)" /work/Refine3D/run.out | tail -10
REMOTE

echo
echo "Refine3D complete. Next: ./05-postprocess.sh"

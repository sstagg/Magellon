#!/usr/bin/env bash
# PostProcess — solvent mask + Heymann masked FSC + Guinier B-factor.
# Operates on Refine3D's two half-maps. ~1 min.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
cd /work

# Build a quick spherical solvent mask. RELION's MaskCreate would be nicer
# (threshold + dilate the average half-map), but for a smoke test a plain
# spherical mask sufficient for FSC weighting is fine.
mkdir -p /work/MaskCreate
/opt/relion/bin/relion_mask_create \
  --i Refine3D/run_class001.mrc \
  --o MaskCreate/mask.mrc \
  --ini_threshold 0.005 \
  --extend_inimask 3 \
  --width_soft_edge 6 \
  --j 4

mkdir -p /work/PostProcess
/opt/relion/bin/relion_postprocess \
  --i Refine3D/run_half1_class001_unfil.mrc \
  --o PostProcess/postprocess \
  --mask MaskCreate/mask.mrc \
  --auto_bfac \
  --autob_lowres 10 \
  --angpix 0.885 \
  2>&1 | tee /work/PostProcess/run.out | tail -50

echo
echo "=== reported resolution ==="
grep -iE "(resolution|FSC.*0.143)" /work/PostProcess/run.out | tail -5
REMOTE

echo
echo "PostProcess complete. Pull results: ./06-fetch-results.sh"

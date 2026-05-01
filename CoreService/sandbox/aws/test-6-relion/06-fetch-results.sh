#!/usr/bin/env bash
# Pull the relevant outputs from /work on the instance back to outputs/ here.
# Skip the bulky particle stacks + intermediate iteration files.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

OUT="${SCRIPT_DIR}/outputs"
mkdir -p "$OUT"

# Pull a curated set of files via scp (rsync isn't always present in
# git-bash on Windows). Stage them on the instance into a tarball first.
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'STAGE'
set -euxo pipefail
mkdir -p /tmp/results-bundle/{Class2D,Class3D,Refine3D,PostProcess,MaskCreate}
cp /work/Class2D/run.out                         /tmp/results-bundle/Class2D/
cp /work/Class2D/run_it005_classes.mrcs          /tmp/results-bundle/Class2D/ 2>/dev/null || true
cp /work/Class2D/run_it005_model.star            /tmp/results-bundle/Class2D/
cp /work/Class3D/run.out                         /tmp/results-bundle/Class3D/
cp /work/Class3D/run_it005_class00*.mrc          /tmp/results-bundle/Class3D/ 2>/dev/null || true
cp /work/Class3D/run_it005_model.star            /tmp/results-bundle/Class3D/
cp /work/Refine3D/run.out                        /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_class001.mrc               /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_half1_class001_unfil.mrc   /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_half2_class001_unfil.mrc   /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_model.star                 /tmp/results-bundle/Refine3D/
cp /work/PostProcess/run.out                     /tmp/results-bundle/PostProcess/
cp /work/PostProcess/postprocess*                /tmp/results-bundle/PostProcess/ 2>/dev/null || true
cp /work/MaskCreate/mask.mrc                     /tmp/results-bundle/MaskCreate/
cd /tmp && tar -czf results-bundle.tar.gz results-bundle/
ls -la /tmp/results-bundle.tar.gz
STAGE

scp -o StrictHostKeyChecking=no -i "$KEY_FILE" \
  ubuntu@"$PUBLIC_IP":/tmp/results-bundle.tar.gz "$OUT/"
cd "$OUT" && tar -xzf results-bundle.tar.gz && rm results-bundle.tar.gz

echo
echo "=== fetched ==="
find "$OUT" -type f | sort

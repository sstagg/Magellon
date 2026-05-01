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
mkdir -p /tmp/results-bundle/{Class2D,Class3D,Refine3D,PostProcess,MaskCreate,Inputs}

# === outputs (existing) ===
cp /work/Class2D/run.out                         /tmp/results-bundle/Class2D/
cp /work/Class2D/run_it005_classes.mrcs          /tmp/results-bundle/Class2D/ 2>/dev/null || true
cp /work/Class2D/run_it005_model.star            /tmp/results-bundle/Class2D/
# Iter4 + iter5 model.stars + classes.mrcs for "1-iter convergence" oracle:
# our Rust Class2D runs from iter4 refs and we compare to iter5.
cp /work/Class2D/run_it004_classes.mrcs          /tmp/results-bundle/Class2D/ 2>/dev/null || true
cp /work/Class2D/run_it004_model.star            /tmp/results-bundle/Class2D/ 2>/dev/null || true
cp /work/Class2D/run_it004_data.star             /tmp/results-bundle/Class2D/ 2>/dev/null || true
cp /work/Class2D/run_it005_data.star             /tmp/results-bundle/Class2D/ 2>/dev/null || true

cp /work/Class3D/run.out                         /tmp/results-bundle/Class3D/
cp /work/Class3D/run_it005_class00*.mrc          /tmp/results-bundle/Class3D/ 2>/dev/null || true
cp /work/Class3D/run_it005_model.star            /tmp/results-bundle/Class3D/
cp /work/Class3D/run_it004_class00*.mrc          /tmp/results-bundle/Class3D/ 2>/dev/null || true
cp /work/Class3D/run_it004_model.star            /tmp/results-bundle/Class3D/ 2>/dev/null || true
cp /work/Class3D/run_it005_data.star             /tmp/results-bundle/Class3D/ 2>/dev/null || true

cp /work/Refine3D/run.out                        /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_class001.mrc               /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_half1_class001_unfil.mrc   /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_half2_class001_unfil.mrc   /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_model.star                 /tmp/results-bundle/Refine3D/
cp /work/Refine3D/run_data.star                  /tmp/results-bundle/Refine3D/ 2>/dev/null || true

cp /work/PostProcess/run.out                     /tmp/results-bundle/PostProcess/
cp /work/PostProcess/postprocess*                /tmp/results-bundle/PostProcess/ 2>/dev/null || true
cp /work/MaskCreate/mask.mrc                     /tmp/results-bundle/MaskCreate/

# === inputs — NEW for the F/G/H oracle ===
# These are what RELION's Class2D/Class3D/Refine3D were FED. Our Rust
# port consumes the same inputs (subsampled if huge) and we compare
# against the matching outputs.
INPUT_PARTICLES=/data/Tutorial5.0/Extract/job012/particles.star
INITIAL_MODEL=/data/Tutorial5.0/InitialModel/job015/run_it090_class001.mrc
[ -f "$INITIAL_MODEL" ] || INITIAL_MODEL=/data/Tutorial5.0/InitialModel/job015/run_it020_class001.mrc

cp "$INPUT_PARTICLES" /tmp/results-bundle/Inputs/particles.star
# Subsample particles to 200 — full set is multi-GB; 200 is enough for
# our oracle test (each E-M iter scales linearly with particle count).
mkdir -p /tmp/results-bundle/Inputs/particle_stacks
# Resolve all unique .mrcs files referenced by the STAR.
PARTICLE_DIR=/data/Tutorial5.0
awk '/^[A-Z0-9].*@/' "$INPUT_PARTICLES" 2>/dev/null \
  | awk '{print $1}' | awk -F'@' '{print $2}' | sort -u | head -50 \
  | while read mrcs_rel; do
      src="${PARTICLE_DIR}/${mrcs_rel}"
      if [ -f "$src" ]; then
        # Preserve the relative path under particle_stacks/.
        dst_dir="/tmp/results-bundle/Inputs/particle_stacks/$(dirname "$mrcs_rel")"
        mkdir -p "$dst_dir"
        cp "$src" "$dst_dir/"
      fi
    done

# Initial 3D model (used by Class3D iter1 + Refine3D iter1).
[ -f "$INITIAL_MODEL" ] && cp "$INITIAL_MODEL" /tmp/results-bundle/Inputs/initial_model.mrc

# Save the exact CLI invocations used (for INPUTS.txt provenance).
{
  echo "=== Class2D ==="
  grep -E "(relion_refine|--K|--iter|--particle_diameter)" /work/Class2D/run.out 2>/dev/null | head -3
  echo
  echo "=== Class3D ==="
  grep -E "(relion_refine|--K|--iter|--ref|--particle_diameter)" /work/Class3D/run.out 2>/dev/null | head -3
  echo
  echo "=== Refine3D ==="
  grep -E "(relion_refine|--auto_refine|--ref|--particle_diameter)" /work/Refine3D/run.out 2>/dev/null | head -3
} > /tmp/results-bundle/Inputs/INVOCATIONS.txt

ls -la /tmp/results-bundle/Inputs/ /tmp/results-bundle/Inputs/particle_stacks/ 2>/dev/null | head -25
du -sh /tmp/results-bundle/Inputs/ 2>/dev/null

cd /tmp && tar -czf results-bundle.tar.gz results-bundle/
ls -la /tmp/results-bundle.tar.gz
STAGE

scp -o StrictHostKeyChecking=no -i "$KEY_FILE" \
  ubuntu@"$PUBLIC_IP":/tmp/results-bundle.tar.gz "$OUT/"
cd "$OUT" && tar -xzf results-bundle.tar.gz && rm results-bundle.tar.gz

echo
echo "=== fetched ==="
find "$OUT" -type f | sort

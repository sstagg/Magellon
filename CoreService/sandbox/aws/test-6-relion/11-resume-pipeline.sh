#!/usr/bin/env bash
# Resume the pipeline from 02-class2d (skip 00-launch + 01-fetch).
# Use when 01-fetch-data.sh succeeded but the wrapper aborted before
# kicking off 02-onwards.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

run() {
  local name=$1
  local script=$2
  echo
  echo "=== ${name} ==="
  if ! bash "${SCRIPT_DIR}/${script}"; then
    echo "${name} failed; continuing anyway (some artefacts may still be useful)"
  fi
}

run "02 Class2D"       "02-class2d.sh"
run "03 Class3D"       "03-class3d.sh"
run "04 Refine3D"      "04-refine3d.sh"
run "05 PostProcess"   "05-postprocess.sh"
run "06 fetch results" "06-fetch-results.sh"

ORACLE_DIR="${SCRIPT_DIR}/../../../../magellon-rust-mrc/sandbox/relion-oracle/data/pipeline"
ORACLE_INPUTS_DIR="${SCRIPT_DIR}/../../../../magellon-rust-mrc/sandbox/relion-oracle/data/inputs"
mkdir -p "$ORACLE_DIR" "$ORACLE_INPUTS_DIR"

if [ -d "${SCRIPT_DIR}/outputs/results-bundle" ]; then
  for sub in Class2D Class3D Refine3D PostProcess MaskCreate; do
    if [ -d "${SCRIPT_DIR}/outputs/results-bundle/$sub" ]; then
      rm -rf "$ORACLE_DIR/$sub"
      cp -r "${SCRIPT_DIR}/outputs/results-bundle/$sub" "$ORACLE_DIR/"
    fi
  done
  if [ -d "${SCRIPT_DIR}/outputs/results-bundle/Inputs" ]; then
    rm -rf "$ORACLE_INPUTS_DIR"
    mkdir -p "$ORACLE_INPUTS_DIR"
    cp -r "${SCRIPT_DIR}/outputs/results-bundle/Inputs/." "$ORACLE_INPUTS_DIR/"
  fi
fi

echo
echo "=== teardown ==="
bash "${SCRIPT_DIR}/99-teardown.sh"

echo
echo "=== resume + teardown complete ==="

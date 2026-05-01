#!/usr/bin/env bash
# Wait for the user-data RELION compile to finish, then run the full
# pipeline (01-fetch through 06-fetch-results), then tear down.
#
# 00-launch.sh has a polling bug that can exit before the compile is
# actually done; this script is the resilient driver — keeps polling
# until /opt/relion/bin/relion_refine exists, then proceeds.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

echo "=== waiting for RELION compile to finish ==="
for i in $(seq 1 80); do
  STATUS=$(ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
    'if [ -x /opt/relion/bin/relion_refine ]; then echo READY; \
     elif sudo grep -q "user-data done" /var/log/user-data.log 2>/dev/null; then echo DONE_NO_BIN; \
     else echo BUILDING; fi' 2>/dev/null || echo SSH_FAIL)
  case "$STATUS" in
    READY)
      echo "RELION binary ready at attempt $i"
      break
      ;;
    DONE_NO_BIN)
      echo "user-data finished but no relion binary — compile likely failed"
      ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
        'sudo tail -50 /var/log/user-data.log' 2>/dev/null | head -50
      exit 2
      ;;
    *)
      echo "  poll $i: $STATUS"
      sleep 30
      ;;
  esac
done

# Verify with a real call.
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
  '/opt/relion/bin/relion_refine --version 2>&1 | head -3'

echo
echo "=== 01: fetch tutorial data ==="
bash "${SCRIPT_DIR}/01-fetch-data.sh"

echo
echo "=== 02: Class2D ==="
bash "${SCRIPT_DIR}/02-class2d.sh"

echo
echo "=== 03: Class3D ==="
bash "${SCRIPT_DIR}/03-class3d.sh"

echo
echo "=== 04: Refine3D ==="
bash "${SCRIPT_DIR}/04-refine3d.sh"

echo
echo "=== 05: PostProcess + MaskCreate ==="
bash "${SCRIPT_DIR}/05-postprocess.sh"

echo
echo "=== 06: fetch results (now includes inputs) ==="
bash "${SCRIPT_DIR}/06-fetch-results.sh"

# Re-organise into oracle layout and tear down.
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
echo "=== 99: teardown ==="
bash "${SCRIPT_DIR}/99-teardown.sh"

echo
echo "=== full pipeline + teardown complete ==="
echo "Oracle data refreshed under sandbox/relion-oracle/data/"

#!/usr/bin/env bash
# Resilient driver — wait for the Rust toolchain to be ready, run the
# full magellon-spa pipeline (01-fetch through 07-fetch), tear down.
# Mirrors test-6-relion's 10-run-full-pipeline pattern.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

echo "=== waiting for Rust toolchain ==="
for i in $(seq 1 40); do
  STATUS=$(ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
    'if [ -x /usr/local/bin/cargo ]; then echo READY; \
     elif sudo grep -q "user-data done" /var/log/user-data.log 2>/dev/null; then echo DONE_NO_CARGO; \
     else echo INSTALLING; fi' 2>/dev/null || echo SSH_FAIL)
  case "$STATUS" in
    READY)
      echo "Rust toolchain ready at attempt $i"
      break
      ;;
    DONE_NO_CARGO)
      echo "user-data finished but no cargo — install likely failed"
      ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
        'sudo tail -50 /var/log/user-data.log' 2>/dev/null | head -50
      exit 2
      ;;
    *)
      echo "  poll $i: $STATUS"
      sleep 15
      ;;
  esac
done

run() {
  local name=$1
  local script=$2
  echo
  echo "=== ${name} ==="
  if ! bash "${SCRIPT_DIR}/${script}"; then
    echo "${name} failed; continuing anyway (some artefacts may still be useful)"
  fi
}

run "01 fetch tutorial data" "01-fetch-data.sh"
run "02 build magellon-spa"  "02-build-magellon.sh"
run "03 Class2D"             "03-class2d.sh"
run "04 Class3D"             "04-class3d.sh"
run "05 Refine3D"            "05-refine3d.sh"
run "06 CtfRefine"           "06-ctf-refine.sh"
run "07 fetch results"       "07-fetch-results.sh"

echo
echo "=== teardown ==="
bash "${SCRIPT_DIR}/99-teardown.sh"

echo
echo "=== full magellon-spa pipeline + teardown complete ==="
echo "Outputs: ${SCRIPT_DIR}/outputs/results-bundle/"
echo
echo "Compare against test-6-relion outputs at:"
echo "  ../test-6-relion/outputs/results-bundle/"
echo "  or magellon-rust-mrc/sandbox/relion-oracle/data/pipeline/"

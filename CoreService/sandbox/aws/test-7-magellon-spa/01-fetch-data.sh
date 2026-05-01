#!/usr/bin/env bash
# Fetch the official RELION 5 tutorial dataset onto the instance.
# Same dataset as test-6 — the whole point of test-7 is "same input,
# different implementation". ~3 GB.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
cd /data

DATA_URL="ftp://ftp.mrc-lmb.cam.ac.uk/pub/scheres/relion30_tutorial_data.tar"
PRECALC_URL="ftp://ftp.mrc-lmb.cam.ac.uk/pub/scheres/relion50_tutorial_precalculated_results.tar.gz"

if [ ! -d /data/relion30_tutorial_data ] && [ ! -d /data/relion_tutorial ]; then
  echo "=== downloading tutorial raw data ==="
  wget -q --show-progress "$DATA_URL" -O relion30_tutorial_data.tar
  tar -xf relion30_tutorial_data.tar
fi
if [ ! -d /data/relion50_tutorial_precalculated_results ]; then
  echo "=== downloading precalculated results ==="
  wget -q --show-progress "$PRECALC_URL" -O relion50_tutorial_precalculated_results.tar.gz
  tar -xzf relion50_tutorial_precalculated_results.tar.gz
fi

# Diagnostic: pipe-fail-safe (don't lose the script to SIGPIPE).
echo "=== particles.star locations ==="
{ find /data -name "particles.star" 2>/dev/null || true; } | head -10 || true
echo "=== initial model ==="
{ ls /data/Tutorial5.0/InitialModel/job015/run_it*_class001.mrc 2>/dev/null || true; } | head -3 || true
REMOTE

echo
echo "Next: ./02-build-magellon.sh"

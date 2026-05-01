#!/usr/bin/env bash
# Fetch the official RELION 5 tutorial dataset onto the instance.
# Lives at MRC-LMB FTP — ~3 GB, mirrored at relion.org.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"
source "${SCRIPT_DIR}/.instance-env"

ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'bash -s' <<'REMOTE'
set -euxo pipefail
cd /data

# RELION 5 tutorial dataset (β-galactosidase from Kato/Namba via MRC-LMB).
# Per https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Introduction.html
DATA_URL="ftp://ftp.mrc-lmb.cam.ac.uk/pub/scheres/relion30_tutorial_data.tar"
PRECALC_URL="ftp://ftp.mrc-lmb.cam.ac.uk/pub/scheres/relion50_tutorial_precalculated_results.tar.gz"

if [ ! -d /data/relion30_tutorial_data ] && [ ! -d /data/relion_tutorial ]; then
  echo "=== downloading tutorial raw data ==="
  wget -q --show-progress "$DATA_URL" -O relion30_tutorial_data.tar
  tar -xf relion30_tutorial_data.tar
fi
if [ ! -d /data/relion50_tutorial_precalculated_results ]; then
  echo "=== downloading precalculated results (gives us a particles.star + initial 3D ref) ==="
  wget -q --show-progress "$PRECALC_URL" -O relion50_tutorial_precalculated_results.tar.gz
  tar -xzf relion50_tutorial_precalculated_results.tar.gz
fi

# The data dir is normally extracted as 'relion_tutorial' or 'relion30_tutorial_data'.
ls -la /data | head -20
echo
echo "=== dataset layout (first 30 dirs) ==="
find /data -maxdepth 3 -type d 2>/dev/null | sort | head -30
echo
echo "=== particle STAR files ==="
find /data -name "*particles*.star" 2>/dev/null | head -10
find /data -name "run_data.star" 2>/dev/null | head -10
echo
echo "=== reference 3D maps ==="
find /data -name "*.mrc" -size +500k -size -50M 2>/dev/null | head -10
REMOTE

echo
echo "Next: ./02-class2d.sh"

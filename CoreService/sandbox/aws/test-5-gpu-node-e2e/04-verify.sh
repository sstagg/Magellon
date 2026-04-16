#!/usr/bin/env bash
# Download output .mrc files + plugin logs from EC2, run verification.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

source "${SCRIPT_DIR}/.instance-env"
SSH="ssh -o StrictHostKeyChecking=no -i $KEY_FILE ec2-user@$PUBLIC_IP"
SCP="scp -o StrictHostKeyChecking=no -i $KEY_FILE"
OUTPUTS="${SCRIPT_DIR}/outputs"
mkdir -p "$OUTPUTS"

echo "=== Plugin logs ==="
$SSH 'cd /home/ec2-user/magellon && docker compose logs motioncor 2>&1' > "${OUTPUTS}/plugin.log"
echo "Saved → ${OUTPUTS}/plugin.log  ($(wc -l < "${OUTPUTS}/plugin.log") lines)"

echo
echo "=== Listing output jobs ==="
$SSH 'ls -la /jobs/' 2>&1 || true

echo
echo "=== Downloading output MRC files ==="
$SSH 'find /jobs -name "*.mrc" -type f' > "${OUTPUTS}/remote_mrc_list.txt"
cat "${OUTPUTS}/remote_mrc_list.txt"

while IFS= read -r REMOTE_PATH; do
  BASENAME=$(basename "$REMOTE_PATH")
  DIRNAME=$(basename "$(dirname "$REMOTE_PATH")")
  LOCAL="${OUTPUTS}/${DIRNAME}_${BASENAME}"
  eval $SCP "ec2-user@${PUBLIC_IP}:${REMOTE_PATH}" "'${LOCAL}'" 2>/dev/null || echo "WARN: failed to copy ${REMOTE_PATH}"
done < "${OUTPUTS}/remote_mrc_list.txt"

echo
echo "=== Downloaded files ==="
ls -lh "${OUTPUTS}"/*.mrc 2>/dev/null || echo "No .mrc files downloaded"

echo
echo "=== Running verification ==="
python "${SCRIPT_DIR}/scripts/verify.py" "${OUTPUTS}"
echo
echo "Done. Next: ./99-teardown.sh"

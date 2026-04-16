#!/usr/bin/env bash
# Upload plugin code + compose files via tar+scp (no rsync on Windows git-bash).
# Pull test data from S3 on the instance (much faster than uploading 1 GB from local).

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

ENV_FILE="${SCRIPT_DIR}/.instance-env"
[ -f "$ENV_FILE" ] || { echo "Run 00-launch.sh first"; exit 1; }
source "$ENV_FILE"

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
SSH="ssh $SSH_OPTS -i $KEY_FILE ec2-user@$PUBLIC_IP"
SCP="scp $SSH_OPTS -i $KEY_FILE"

REPO_ROOT="${SCRIPT_DIR}/../../../.."
PLUGIN_DIR="${REPO_ROOT}/plugins/magellon_motioncor_plugin"
SDK_DIR="${REPO_ROOT}/magellon-sdk"

echo "=== Packing plugin source ==="
STAGE="/tmp/${PROJECT}-deploy"
rm -rf "$STAGE" && mkdir -p "$STAGE"
tar czf "${STAGE}/plugin.tar.gz" \
  -C "$(dirname "$PLUGIN_DIR")" \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='app.log*' \
  --exclude='.env' --exclude='venv' --exclude='*.iml' --exclude='.git' \
  "$(basename "$PLUGIN_DIR")"

echo "=== Packing SDK ==="
tar czf "${STAGE}/sdk.tar.gz" \
  -C "$(dirname "$SDK_DIR")" \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
  "$(basename "$SDK_DIR")"

echo "=== Uploading tarballs ==="
$SSH "mkdir -p /home/ec2-user/magellon"
$SCP "${STAGE}/plugin.tar.gz" "ec2-user@${PUBLIC_IP}:/home/ec2-user/magellon/"
$SCP "${STAGE}/sdk.tar.gz" "ec2-user@${PUBLIC_IP}:/home/ec2-user/magellon/"

echo "=== Extracting on instance ==="
$SSH 'cd /home/ec2-user/magellon && \
  tar xzf plugin.tar.gz && mv magellon_motioncor_plugin plugin 2>/dev/null; \
  tar xzf sdk.tar.gz && rm -f plugin.tar.gz sdk.tar.gz'

echo "=== Overriding requirements for Docker build (use .whl, not editable install) ==="
$SSH 'cp /home/ec2-user/magellon/plugin/requirements.docker.txt /home/ec2-user/magellon/plugin/requirements.txt'

echo "=== Fixing MC2 binary permissions ==="
$SSH 'chmod +x /home/ec2-user/magellon/plugin/motioncor2_binaryfiles/MotionCor2_*'

echo "=== Patching Dockerfile to COPY SDK .whl before pip install ==="
$SSH 'cd /home/ec2-user/magellon/plugin && grep -q "COPY magellon_sdk" Dockerfile || sed -i "/COPY requirements.txt/i COPY magellon_sdk-0.1.0-py3-none-any.whl ./" Dockerfile'

echo "=== Uploading settings_prod.yml ==="
$SCP "${SCRIPT_DIR}/compose/settings_prod.yml" "ec2-user@${PUBLIC_IP}:/home/ec2-user/magellon/plugin/configs/settings_prod.yml"

echo "=== Uploading docker-compose.yml ==="
$SCP "${SCRIPT_DIR}/compose/docker-compose.yml" "ec2-user@${PUBLIC_IP}:/home/ec2-user/magellon/docker-compose.yml"

echo "=== Pulling test data from S3 (in-region, fast) ==="
$SSH "sudo chown -R ec2-user:ec2-user /data"
for EX in example1 example2; do
  echo "  ${EX}..."
  $SSH "mkdir -p /data/${EX} && aws s3 cp s3://${S3_TEST_BUCKET}/Magellon-test/Magellon-test/${EX}/ /data/${EX}/ --recursive --exclude 'output.mrc' --exclude '*.txt' 2>&1 | tail -3"
done

echo "=== Generating synthetic gain on instance ==="
$SSH 'pip3 install --quiet tifffile mrcfile numpy 2>/dev/null || pip install --quiet tifffile mrcfile numpy 2>/dev/null'
$SSH 'python3 << "PYEOF"
import numpy as np, tifffile, mrcfile, glob
tif = glob.glob("/data/example1/*.tif")[0]
with tifffile.TiffFile(tif) as t:
    H, W = t.pages[0].shape[-2], t.pages[0].shape[-1]
    print(f"Frame dims: {H} x {W}")
gain = np.ones((H, W), dtype=np.float32)
with mrcfile.new("/data/gain_ones.mrc", overwrite=True) as f:
    f.set_data(gain)
print("Wrote /data/gain_ones.mrc")
PYEOF'

echo "=== Listing /data ==="
$SSH 'find /data -type f | head -20'

echo "=== Building plugin image (first time ~3-5 min) ==="
$SSH 'cd /home/ec2-user/magellon && docker compose build 2>&1' | tail -40

echo "=== Starting services ==="
$SSH 'cd /home/ec2-user/magellon && docker compose up -d 2>&1'

echo
echo "Deploy done. Next: ./02-wait-ready.sh"

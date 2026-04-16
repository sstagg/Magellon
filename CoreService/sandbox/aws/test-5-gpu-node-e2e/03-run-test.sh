#!/usr/bin/env bash
# Run the test publisher from Windows against the remote EC2 RabbitMQ.
# Submits 2 tasks and waits for results.

set -euo pipefail
export MSYS_NO_PATHCONV=1
export MSYS2_ENV_CONV_EXCL="REMOTE_DATA_ROOT;GAIN_PATH"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

source "${SCRIPT_DIR}/.instance-env"

PLUGIN_DIR="${SCRIPT_DIR}/../../../plugins/magellon_motioncor_plugin"
OUTPUTS="${SCRIPT_DIR}/outputs"
mkdir -p "$OUTPUTS"

echo "=== Run 1: submit 2 tasks ==="
export RABBIT_HOST="$PUBLIC_IP"
export REMOTE_DATA_ROOT="/data"
export GAIN_PATH="/data/gain_ones.mrc"

cd "$PLUGIN_DIR"
python test_batch_publish.py --count 2 --timeout 600 2>&1 | tee "${OUTPUTS}/run1.log"
RC1=${PIPESTATUS[0]}

echo
echo "=== Run 2: repeat same 2 tasks (repeatability check) ==="
python test_batch_publish.py --count 2 --timeout 600 2>&1 | tee "${OUTPUTS}/run2.log"
RC2=${PIPESTATUS[0]}

echo
echo "Run 1 exit: $RC1"
echo "Run 2 exit: $RC2"
echo
echo "Next: ./04-verify.sh"

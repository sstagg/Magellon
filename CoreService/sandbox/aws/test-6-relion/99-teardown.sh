#!/usr/bin/env bash
# Tear down everything created by 00-launch.sh: instance, SG, key pair.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"; source "${SCRIPT_DIR}/../common/activate.sh"; SCRIPT_DIR="$MY_DIR"

if [ ! -f "${SCRIPT_DIR}/.instance-env" ]; then
  echo "No .instance-env — nothing to tear down."
  exit 0
fi
source "${SCRIPT_DIR}/.instance-env"

echo "Terminating instance ${INSTANCE_ID}..."
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --output text >/dev/null
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
echo "Instance terminated."

echo "Deleting security group ${SG_ID}..."
aws ec2 delete-security-group --group-id "$SG_ID" 2>&1 | head -5 || true

echo "Deleting key pair ${KEY_NAME}..."
aws ec2 delete-key-pair --key-name "$KEY_NAME" 2>&1 | head -5 || true
rm -f "$KEY_FILE"

rm -f "${SCRIPT_DIR}/.instance-env"
echo "Done."

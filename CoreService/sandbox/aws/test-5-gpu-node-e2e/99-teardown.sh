#!/usr/bin/env bash
# Terminate the EC2 instance + delete SG + key pair. Idempotent.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

ENV_FILE="${SCRIPT_DIR}/.instance-env"
[ -f "$ENV_FILE" ] || { echo "No .instance-env — nothing to tear down."; exit 0; }
source "$ENV_FILE"

SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i $KEY_FILE ec2-user@$PUBLIC_IP"

echo "=== Saving final logs ==="
OUTPUTS="${SCRIPT_DIR}/outputs"
mkdir -p "$OUTPUTS"
$SSH 'cd /home/ec2-user/magellon && docker compose logs 2>&1' > "${OUTPUTS}/compose-final.log" 2>/dev/null || true
echo "Saved compose-final.log"

echo
echo "=== Terminating instance ${INSTANCE_ID} ==="
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --query 'TerminatingInstances[0].CurrentState.Name' --output text || true

echo "Waiting for terminated state..."
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" 2>/dev/null || true

echo
echo "=== Deleting SG ${SG_ID} ==="
aws ec2 delete-security-group --group-id "$SG_ID" 2>/dev/null || echo "SG delete failed (may still be draining)"

echo
echo "=== Deleting key pair ${KEY_NAME} ==="
aws ec2 delete-key-pair --key-name "$KEY_NAME" 2>/dev/null || true
rm -f "$KEY_FILE"

echo
echo "=== Tag audit ==="
bash "${SCRIPT_DIR}/../common/tag-audit.sh" 2>&1 || true

echo
rm -f "$ENV_FILE"
echo "Teardown complete."

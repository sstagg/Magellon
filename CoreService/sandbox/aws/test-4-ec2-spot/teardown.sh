#!/usr/bin/env bash
# Clean up orphans: any stopped/terminated spot instance leftovers, the SG, the log group.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

SG_NAME="${PROJECT}-ec2-spot-sg"
LG_NAME="/aws/ec2/${PROJECT}-baseline"

echo "Terminating any running project-tagged EC2 instances..."
IDS=$(aws ec2 describe-instances --filters "Name=tag:Project,Values=${PROJECT}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$IDS" ] && [ "$IDS" != "None" ]; then
  echo "  $IDS"
  aws ec2 terminate-instances --instance-ids $IDS >/dev/null
  aws ec2 wait instance-terminated --instance-ids $IDS || true
fi

SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  echo "Deleting SG $SG_ID..."
  aws ec2 delete-security-group --group-id "$SG_ID" 2>&1 | grep -v "does not exist" || true
fi

echo "Deleting log group..."
aws logs delete-log-group --log-group-name "$LG_NAME" 2>/dev/null || true

echo "Done."

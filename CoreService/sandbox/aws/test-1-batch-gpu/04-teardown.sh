#!/usr/bin/env bash
# Disable + delete Batch resources. IAM roles are left in place for reuse. SG is deleted.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

CE_NAME="${PROJECT}-ce-spot-g4dn"
QUEUE_NAME="${PROJECT}-queue"
JD_NAME="${PROJECT}-motioncor"
SG_NAME="${PROJECT}-batch-sg"

# 1. Disable + delete queue
if aws batch describe-job-queues --job-queues "$QUEUE_NAME" --query 'jobQueues[0].state' --output text 2>/dev/null | grep -q ENABLED; then
  echo "Disabling queue..."
  aws batch update-job-queue --job-queue "$QUEUE_NAME" --state DISABLED >/dev/null
  for _ in $(seq 1 30); do
    S=$(aws batch describe-job-queues --job-queues "$QUEUE_NAME" --query 'jobQueues[0].status' --output text)
    echo "  queue $S"
    [ "$S" = "VALID" ] || [ "$S" = "UPDATING" ] || break
    [ "$S" = "VALID" ] && break
    sleep 5
  done
fi
aws batch delete-job-queue --job-queue "$QUEUE_NAME" 2>/dev/null || echo "  (queue gone)"

# 2. Deregister job definition (all revisions)
for ARN in $(aws batch describe-job-definitions --job-definition-name "$JD_NAME" --status ACTIVE --query 'jobDefinitions[].jobDefinitionArn' --output text 2>/dev/null); do
  echo "Deregistering $ARN"
  aws batch deregister-job-definition --job-definition "$ARN" || true
done

# 3. Wait for queue deletion to finalize before disabling CE
sleep 10

# 4. Disable + delete compute env
if aws batch describe-compute-environments --compute-environments "$CE_NAME" --query 'computeEnvironments[0].state' --output text 2>/dev/null | grep -q ENABLED; then
  echo "Disabling CE..."
  aws batch update-compute-environment --compute-environment "$CE_NAME" --state DISABLED >/dev/null
  for _ in $(seq 1 60); do
    S=$(aws batch describe-compute-environments --compute-environments "$CE_NAME" --query 'computeEnvironments[0].status' --output text)
    echo "  CE $S"
    [ "$S" = "VALID" ] && break
    sleep 5
  done
fi
aws batch delete-compute-environment --compute-environment "$CE_NAME" 2>/dev/null || echo "  (CE gone)"

# 5. SG — wait for instances to drain before deleting
echo "Waiting for any spot instances to terminate..."
sleep 30
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  aws ec2 delete-security-group --group-id "$SG_ID" 2>&1 | grep -v "does not exist" || true
fi

echo "Done."

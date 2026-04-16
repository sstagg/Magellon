#!/usr/bin/env bash
# Create (or update) Batch job queue and job definition.
# Job def requests 1 GPU, 7 vCPU, 28 GB RAM — fits inside g4dn.2xlarge (8 vCPU, 32GB, 1x T4).
# NOTE: g4dn.xlarge was tried first and kernel-OOMs — see results/test-1-batch-gpu.md.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

CE_NAME="${PROJECT}-ce-spot-g4dn2xl"
QUEUE_NAME="${PROJECT}-queue"
JD_NAME="${PROJECT}-motioncor"

# --- Job queue ---
EXISTING=$(aws batch describe-job-queues --job-queues "$QUEUE_NAME" --query 'jobQueues[0].state' --output text 2>/dev/null || echo "")
if [ -z "$EXISTING" ] || [ "$EXISTING" = "None" ]; then
  echo "Creating queue ${QUEUE_NAME}..."
  aws batch create-job-queue \
    --job-queue-name "$QUEUE_NAME" \
    --state ENABLED --priority 1 \
    --compute-environment-order "order=1,computeEnvironment=${CE_NAME}" \
    --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" >/dev/null
else
  echo "Queue ${QUEUE_NAME} exists."
fi

# --- Job definition ---
JOB_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_BATCH_JOB}"

read -r -d '' CONTAINER <<EOF || true
{
  "image": "${ECR_URI}:latest",
  "command": ["env"],
  "jobRoleArn": "${JOB_ROLE_ARN}",
  "resourceRequirements": [
    {"type": "VCPU",   "value": "7"},
    {"type": "MEMORY", "value": "28000"},
    {"type": "GPU",    "value": "1"}
  ],
  "logConfiguration": {"logDriver": "awslogs"}
}
EOF

echo "Registering job definition ${JD_NAME} (new revision each time)..."
aws batch register-job-definition \
  --job-definition-name "$JD_NAME" \
  --type container \
  --platform-capabilities EC2 \
  --container-properties "$CONTAINER" \
  --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" \
  --query '{name:jobDefinitionName,rev:revision,arn:jobDefinitionArn}' --output table

echo
echo "Done. Next: ./03-submit.sh"

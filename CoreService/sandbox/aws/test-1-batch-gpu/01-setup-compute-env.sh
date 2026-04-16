#!/usr/bin/env bash
# Create egress-only SG + Batch spot compute env on g4dn.xlarge. Idempotent.
# Uses BEST_FIT_PROGRESSIVE with SPOT (no explicit spotIamFleetRole needed — AWS Batch uses the
# AWSServiceRoleForEC2Spot service-linked role).

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

SG_NAME="${PROJECT}-batch-sg"
# NOTE: g4dn.2xlarge (32 GB host) — xlarge is OOM-killed. See results/test-1-batch-gpu.md.
CE_NAME="${PROJECT}-ce-spot-g4dn2xl"

# Default Batch AMI (at least in our region/account) picks Amazon Linux 2023 WITHOUT the ECS
# agent — instances boot but never register with the ECS cluster so jobs stay in RUNNABLE forever.
# Pin the ECS-optimized GPU AMI explicitly (AL2 + ECS agent + NVIDIA drivers).
ECS_GPU_AMI=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=amzn2-ami-ecs-gpu-hvm-*" "Name=state,Values=available" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
echo "Using ECS-GPU AMI: ${ECS_GPU_AMI}"

# --- Security group (egress only) ---
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "Creating SG ${SG_NAME}..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "Egress-only SG for ${PROJECT} Batch jobs" \
    --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" \
    --query GroupId --output text)
  # Default SG has no inbound; default egress = all. Leave as-is.
else
  echo "SG ${SG_NAME} exists: $SG_ID"
fi

INSTANCE_PROFILE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:instance-profile/${ROLE_BATCH_INSTANCE}"
SERVICE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_BATCH_SERVICE}"

read -r -d '' CE_CR <<EOF || true
{
  "type": "SPOT",
  "allocationStrategy": "BEST_FIT_PROGRESSIVE",
  "minvCpus": 0,
  "maxvCpus": 8,
  "desiredvCpus": 0,
  "instanceTypes": ["g4dn.2xlarge"],
  "subnets": $(echo "$SUBNETS" | awk -F, '{printf "["; for(i=1;i<=NF;i++){if(i>1)printf ","; printf "\""$i"\""} printf "]"}'),
  "securityGroupIds": ["${SG_ID}"],
  "instanceRole": "${INSTANCE_PROFILE_ARN}",
  "imageId": "${ECS_GPU_AMI}",
  "bidPercentage": 100,
  "tags": {"Project":"${PROJECT}","Owner":"${OWNER}","CostCenter":"${COST_CENTER}"}
}
EOF

EXISTING=$(aws batch describe-compute-environments --compute-environments "$CE_NAME" --query 'computeEnvironments[0].status' --output text 2>/dev/null || echo "")
if [ -z "$EXISTING" ] || [ "$EXISTING" = "None" ]; then
  echo "Creating compute env ${CE_NAME}..."
  aws batch create-compute-environment \
    --compute-environment-name "$CE_NAME" \
    --type MANAGED \
    --state ENABLED \
    --service-role "$SERVICE_ROLE_ARN" \
    --compute-resources "$CE_CR" \
    --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" >/dev/null
else
  echo "CE ${CE_NAME} exists (status=$EXISTING)"
fi

echo "Waiting for CE to be VALID + ENABLED..."
for _ in $(seq 1 60); do
  S=$(aws batch describe-compute-environments --compute-environments "$CE_NAME" --query 'computeEnvironments[0].[status,state]' --output text 2>/dev/null || echo "CREATING ENABLED")
  echo "  $S"
  [[ "$S" == "VALID"* ]] && break
  sleep 5
done

echo
echo "Done. SG=${SG_ID}  CE=${CE_NAME}"
echo "Next: ./02-setup-queue-and-def.sh"

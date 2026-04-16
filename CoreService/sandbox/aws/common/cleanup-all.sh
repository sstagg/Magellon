#!/usr/bin/env bash
# Nuke everything tagged Project=magellon-gpu-eval. Use with caution.
# Order matters: drain resources with active workloads first.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

read -p "Delete EVERYTHING tagged Project=${PROJECT}? Type the project name to confirm: " CONFIRM
[ "$CONFIRM" = "$PROJECT" ] || { echo "aborted"; exit 1; }

echo "=== Batch ==="
bash "${SCRIPT_DIR}/../test-1-batch-gpu/04-teardown.sh" || true

echo "=== Upload pipeline ==="
bash "${SCRIPT_DIR}/../upload-pipeline/teardown.sh" || true

echo "=== EC2 spot ==="
bash "${SCRIPT_DIR}/../test-4-ec2-spot/teardown.sh" || true

echo "=== SageMaker endpoints (async) ==="
for EP in $(aws sagemaker list-endpoints --tags Key=Project,Value="${PROJECT}" --query 'Endpoints[].EndpointName' --output text 2>/dev/null || true); do
  aws sagemaker delete-endpoint --endpoint-name "$EP" || true
done
for EC in $(aws sagemaker list-endpoint-configs --query 'EndpointConfigs[].EndpointConfigName' --output text 2>/dev/null | tr '\t' '\n' | grep "^${PROJECT}" || true); do
  aws sagemaker delete-endpoint-config --endpoint-config-name "$EC" || true
done
for M in $(aws sagemaker list-models --query 'Models[].ModelName' --output text 2>/dev/null | tr '\t' '\n' | grep "^${PROJECT}" || true); do
  aws sagemaker delete-model --model-name "$M" || true
done

echo "=== ECR repo ==="
aws ecr delete-repository --repository-name "$ECR_REPO" --force 2>/dev/null || true

echo "=== S3 buckets (work bucket only — test bucket is shared) ==="
aws s3 rm "s3://${S3_WORK_BUCKET}" --recursive 2>/dev/null || true
aws s3api delete-bucket --bucket "$S3_WORK_BUCKET" 2>/dev/null || true

echo "=== IAM roles ==="
for R in "$ROLE_BATCH_SERVICE" "$ROLE_BATCH_INSTANCE" "$ROLE_BATCH_JOB" "$ROLE_SAGEMAKER_EXEC" "$ROLE_LAMBDA_EXEC"; do
  # Detach managed
  for P in $(aws iam list-attached-role-policies --role-name "$R" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do
    aws iam detach-role-policy --role-name "$R" --policy-arn "$P" 2>/dev/null || true
  done
  # Delete inline
  for P in $(aws iam list-role-policies --role-name "$R" --query 'PolicyNames[]' --output text 2>/dev/null); do
    aws iam delete-role-policy --role-name "$R" --policy-name "$P" 2>/dev/null || true
  done
  # Instance profile
  if aws iam get-instance-profile --instance-profile-name "$R" >/dev/null 2>&1; then
    aws iam remove-role-from-instance-profile --instance-profile-name "$R" --role-name "$R" 2>/dev/null || true
    aws iam delete-instance-profile --instance-profile-name "$R" 2>/dev/null || true
  fi
  aws iam delete-role --role-name "$R" 2>/dev/null || true
done

echo "=== Budget ==="
aws budgets delete-budget --account-id "$AWS_ACCOUNT_ID" --budget-name "$PROJECT" 2>/dev/null || true

echo "Done. Verify with: common/tag-audit.sh"

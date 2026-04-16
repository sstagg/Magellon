#!/usr/bin/env bash
# Create all IAM roles this project needs. Idempotent: if a role exists, just reattach policies.
# If SCPs block iam:CreateRole, re-run after confirming with FSU admin which service roles exist.
#
# Roles:
#   ${ROLE_BATCH_SERVICE}    - Batch control plane
#   ${ROLE_BATCH_INSTANCE}   - Batch EC2 (ECS) instance
#   ${ROLE_BATCH_JOB}        - container runtime (S3 read/write)
#   ${ROLE_SAGEMAKER_EXEC}   - SageMaker exec (ECR pull, S3 read/write, logs)
#   ${ROLE_LAMBDA_EXEC}      - upload-pipeline Lambdas (S3, Batch submit, logs)

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

trust_policy () {
  local principal="$1"
  cat <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"${principal}"},"Action":"sts:AssumeRole"}]}
EOF
}

create_or_update_role () {
  local name="$1"; local principal="$2"; shift 2
  local managed_policies=("$@")

  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    echo "Role ${name} exists."
  else
    echo "Creating role ${name}..."
    aws iam create-role \
      --role-name "$name" \
      --assume-role-policy-document "$(trust_policy "$principal")" \
      --tags ${TAGS_CLI} >/dev/null
  fi

  for p in "${managed_policies[@]}"; do
    aws iam attach-role-policy --role-name "$name" --policy-arn "$p" || true
  done
}

# --- Batch service role ---
create_or_update_role "$ROLE_BATCH_SERVICE" "batch.amazonaws.com" \
  arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole

# --- Batch EC2 instance role (for the GPU nodes in the compute env) ---
create_or_update_role "$ROLE_BATCH_INSTANCE" "ec2.amazonaws.com" \
  arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role \
  arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Instance profile wraps the instance role for EC2
if ! aws iam get-instance-profile --instance-profile-name "$ROLE_BATCH_INSTANCE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$ROLE_BATCH_INSTANCE" --tags ${TAGS_CLI} >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE_BATCH_INSTANCE" --role-name "$ROLE_BATCH_INSTANCE"
fi

# --- Batch job role (container runtime identity) ---
create_or_update_role "$ROLE_BATCH_JOB" "ecs-tasks.amazonaws.com"

# Inline policy: read test bucket + read/write work bucket
JOB_POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:GetObject","s3:ListBucket"],"Resource":["arn:aws:s3:::${S3_TEST_BUCKET}","arn:aws:s3:::${S3_TEST_BUCKET}/*"]},
  {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:ListBucket","s3:DeleteObject"],"Resource":["arn:aws:s3:::${S3_WORK_BUCKET}","arn:aws:s3:::${S3_WORK_BUCKET}/*"]},
  {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents","logs:CreateLogGroup"],"Resource":"*"}
]}
EOF
)
aws iam put-role-policy --role-name "$ROLE_BATCH_JOB" --policy-name "job-s3-logs" --policy-document "$JOB_POLICY"

# --- SageMaker execution role ---
create_or_update_role "$ROLE_SAGEMAKER_EXEC" "sagemaker.amazonaws.com" \
  arn:aws:iam::aws:policy/AmazonSageMakerFullAccess \
  arn:aws:iam::aws:policy/AmazonS3FullAccess \
  arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

# --- Lambda execution role (upload pipeline) ---
create_or_update_role "$ROLE_LAMBDA_EXEC" "lambda.amazonaws.com" \
  arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

LAMBDA_POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:PutObject","s3:GetObject","s3:ListBucket","s3:DeleteObject"],"Resource":["arn:aws:s3:::${S3_WORK_BUCKET}","arn:aws:s3:::${S3_WORK_BUCKET}/*"]},
  {"Effect":"Allow","Action":["batch:SubmitJob","batch:DescribeJobs"],"Resource":"*"},
  {"Effect":"Allow","Action":["sagemaker:InvokeEndpointAsync","sagemaker:InvokeEndpoint"],"Resource":"*"}
]}
EOF
)
aws iam put-role-policy --role-name "$ROLE_LAMBDA_EXEC" --policy-name "upload-pipeline" --policy-document "$LAMBDA_POLICY"

echo
echo "Done. ARNs:"
for r in "$ROLE_BATCH_SERVICE" "$ROLE_BATCH_INSTANCE" "$ROLE_BATCH_JOB" "$ROLE_SAGEMAKER_EXEC" "$ROLE_LAMBDA_EXEC"; do
  aws iam get-role --role-name "$r" --query "Role.Arn" --output text
done

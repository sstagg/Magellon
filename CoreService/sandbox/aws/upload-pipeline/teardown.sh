#!/usr/bin/env bash
# Remove Lambdas, Function URL, S3 notification, SSM param. Keeps the bucket.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

API_FN="${PROJECT}-upload-api"
EVENT_FN="${PROJECT}-on-upload"

echo "Removing S3 notification..."
aws s3api put-bucket-notification-configuration --bucket "$S3_WORK_BUCKET" \
  --notification-configuration '{}' || true

echo "Deleting Lambdas..."
aws lambda delete-function-url-config --function-name "$API_FN" 2>/dev/null || true
aws lambda delete-function --function-name "$API_FN" 2>/dev/null || true
aws lambda delete-function --function-name "$EVENT_FN" 2>/dev/null || true

echo "Deleting SSM key param..."
aws ssm delete-parameter --name "/${PROJECT}/upload-api/key" 2>/dev/null || true

echo "Done."

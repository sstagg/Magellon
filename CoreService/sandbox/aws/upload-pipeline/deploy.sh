#!/usr/bin/env bash
# Deploy the two Lambdas + Function URL + S3 event notification. Idempotent.
# Prereqs: common/00-setup-iam.sh + common/03-setup-buckets.sh + test-1-batch-gpu resources
# (queue + job def) already exist.

set -euo pipefail
# Windows git-bash / MSYS mangles leading-slash CLI args ("/magellon-..." → "C:/Program Files/Git/...").
# Disable that so AWS CLI receives SSM parameter paths unchanged.
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$DEPLOY_DIR"  # activate.sh overwrites SCRIPT_DIR — restore ours

API_FN="${PROJECT}-upload-api"
EVENT_FN="${PROJECT}-on-upload"
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_LAMBDA_EXEC}"
BATCH_QUEUE="${PROJECT}-queue"
BATCH_JOB_DEF="${PROJECT}-motioncor"

# Generate/reuse API key (stashed in parameter store so redeploys don't rotate it)
SSM_NAME="/${PROJECT}/upload-api/key"
API_KEY=$(aws ssm get-parameter --name "$SSM_NAME" --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || echo "")
if [ -z "$API_KEY" ]; then
  API_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))" 2>/dev/null || python3 -c "import secrets;print(secrets.token_urlsafe(32))")
  aws ssm put-parameter --name "$SSM_NAME" --value "$API_KEY" --type SecureString --tags "Key=Project,Value=${PROJECT}"
  echo "Generated new API key, stored at SSM ${SSM_NAME}"
fi

# --- Package + deploy API Lambda ---
# Cross-platform zip helper: uses `zip` if available, else Python's zipfile.
zip_dir() {
  local dir="$1"
  local out="$2"
  if command -v zip >/dev/null 2>&1; then
    ( cd "$dir" && zip -q -r "$out" . )
  else
    ( cd "$dir" && python -c "
import sys, os, zipfile
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk('.'):
        for f in files:
            if f == os.path.basename(out):
                continue
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, '.'))
" "$out" )
  fi
}

# If aws.exe is a Windows-native binary, it won't resolve /tmp-style paths.
# Convert unix paths to Windows-native when needed.
winpath() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    echo "$1"
  fi
}

STAGE="/tmp/${PROJECT}-upload-api"
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp "${SCRIPT_DIR}/handlers/upload_api.py" "$STAGE/"
zip_dir "$STAGE" "pkg.zip"
STAGE_ZIP_WIN=$(winpath "${STAGE}/pkg.zip")

if aws lambda get-function --function-name "$API_FN" >/dev/null 2>&1; then
  echo "Updating ${API_FN} code..."
  aws lambda update-function-code --function-name "$API_FN" --zip-file "fileb://${STAGE_ZIP_WIN}" >/dev/null
  aws lambda wait function-updated --function-name "$API_FN"
  aws lambda update-function-configuration --function-name "$API_FN" \
    --environment "Variables={WORK_BUCKET=${S3_WORK_BUCKET},API_KEY=${API_KEY},BATCH_QUEUE=${BATCH_QUEUE}}" \
    --role "$ROLE_ARN" --timeout 10 --memory-size 256 >/dev/null
else
  echo "Creating ${API_FN}..."
  aws lambda create-function --function-name "$API_FN" \
    --runtime python3.11 --role "$ROLE_ARN" \
    --handler upload_api.handler \
    --zip-file "fileb://${STAGE_ZIP_WIN}" \
    --timeout 10 --memory-size 256 \
    --environment "Variables={WORK_BUCKET=${S3_WORK_BUCKET},API_KEY=${API_KEY},BATCH_QUEUE=${BATCH_QUEUE}}" \
    --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" >/dev/null
fi

# --- Function URL (auth NONE — we check API key inside the handler) ---
if ! aws lambda get-function-url-config --function-name "$API_FN" >/dev/null 2>&1; then
  aws lambda create-function-url-config --function-name "$API_FN" \
    --auth-type NONE --cors '{"AllowOrigins":["*"],"AllowMethods":["*"],"AllowHeaders":["content-type","x-api-key"],"MaxAge":86400}' >/dev/null
  # Allow public invoke (handler enforces API key)
  aws lambda add-permission --function-name "$API_FN" \
    --statement-id FunctionUrlAllowPublicAccess \
    --action lambda:InvokeFunctionUrl --principal "*" \
    --function-url-auth-type NONE 2>&1 | grep -v ResourceConflict || true
fi
API_URL=$(aws lambda get-function-url-config --function-name "$API_FN" --query 'FunctionUrl' --output text)

# --- on-upload Lambda ---
STAGE2="/tmp/${PROJECT}-on-upload"
rm -rf "$STAGE2" && mkdir -p "$STAGE2"
cp "${SCRIPT_DIR}/handlers/on_upload.py" "$STAGE2/"
zip_dir "$STAGE2" "pkg.zip"
STAGE2_ZIP_WIN=$(winpath "${STAGE2}/pkg.zip")

if aws lambda get-function --function-name "$EVENT_FN" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$EVENT_FN" --zip-file "fileb://${STAGE2_ZIP_WIN}" >/dev/null
  aws lambda wait function-updated --function-name "$EVENT_FN"
  aws lambda update-function-configuration --function-name "$EVENT_FN" \
    --environment "Variables={WORK_BUCKET=${S3_WORK_BUCKET},BATCH_QUEUE=${BATCH_QUEUE},BATCH_JOB_DEF=${BATCH_JOB_DEF}}" \
    --role "$ROLE_ARN" --timeout 30 --memory-size 256 >/dev/null
else
  aws lambda create-function --function-name "$EVENT_FN" \
    --runtime python3.11 --role "$ROLE_ARN" \
    --handler on_upload.handler \
    --zip-file "fileb://${STAGE2_ZIP_WIN}" \
    --timeout 30 --memory-size 256 \
    --environment "Variables={WORK_BUCKET=${S3_WORK_BUCKET},BATCH_QUEUE=${BATCH_QUEUE},BATCH_JOB_DEF=${BATCH_JOB_DEF}}" \
    --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER}" >/dev/null
fi
EVENT_FN_ARN=$(aws lambda get-function --function-name "$EVENT_FN" --query 'Configuration.FunctionArn' --output text)

# --- S3 → Lambda permission + notification ---
aws lambda add-permission --function-name "$EVENT_FN" \
  --statement-id S3InvokeOnUpload \
  --action lambda:InvokeFunction --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::${S3_WORK_BUCKET}" 2>&1 | grep -v ResourceConflict || true

aws s3api put-bucket-notification-configuration --bucket "$S3_WORK_BUCKET" \
  --notification-configuration '{
    "LambdaFunctionConfigurations":[{
      "Id":"on-upload",
      "LambdaFunctionArn":"'$EVENT_FN_ARN'",
      "Events":["s3:ObjectCreated:*"],
      "Filter":{"Key":{"FilterRules":[{"Name":"prefix","Value":"uploads/"}]}}
    }]
  }'

echo
echo "============================================================"
echo "Upload pipeline deployed."
echo "  API URL : ${API_URL}"
echo "  API Key : ${API_KEY}"
echo "  Bucket  : s3://${S3_WORK_BUCKET}/"
echo
echo "Paste API_URL + API_KEY into web/index.html, then open it in a browser."
echo "============================================================"

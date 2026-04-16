#!/usr/bin/env bash
# Create the work bucket used by all tests + upload pipeline. Idempotent.
#   - Block Public Access ON (presigned URLs still work — they're signed, not anonymous)
#   - 7-day lifecycle so stale test data doesn't accumulate
#   - CORS allows browser uploads from anywhere (tighten for prod)

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

B="$S3_WORK_BUCKET"

if aws s3api head-bucket --bucket "$B" 2>/dev/null; then
  echo "Bucket ${B} exists."
else
  echo "Creating bucket ${B}..."
  # us-east-1 does not accept LocationConstraint — special case
  if [ "$AWS_DEFAULT_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$B"
  else
    aws s3api create-bucket --bucket "$B" \
      --create-bucket-configuration LocationConstraint="$AWS_DEFAULT_REGION"
  fi
  aws s3api put-bucket-tagging --bucket "$B" \
    --tagging '{"TagSet":'"${TAGS_JSON}"'}'
fi

echo "Block all public access..."
aws s3api put-public-access-block --bucket "$B" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "7-day lifecycle..."
aws s3api put-bucket-lifecycle-configuration --bucket "$B" \
  --lifecycle-configuration '{"Rules":[{"ID":"expire-7d","Status":"Enabled","Filter":{"Prefix":""},"Expiration":{"Days":7},"AbortIncompleteMultipartUpload":{"DaysAfterInitiation":1}}]}'

echo "CORS (permissive for demo; tighten for prod)..."
aws s3api put-bucket-cors --bucket "$B" \
  --cors-configuration '{"CORSRules":[{"AllowedOrigins":["*"],"AllowedMethods":["GET","PUT","POST","HEAD"],"AllowedHeaders":["*"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3000}]}'

echo "Done. Bucket: s3://${B}/"

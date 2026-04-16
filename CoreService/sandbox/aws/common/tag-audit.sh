#!/usr/bin/env bash
# List every resource tagged Project=magellon-gpu-eval. Run anytime to see what's alive.
# Usage: common/tag-audit.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

echo "=== Resources tagged Project=${PROJECT} in ${AWS_DEFAULT_REGION} ==="
aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=${PROJECT}" \
  --query 'ResourceTagMappingList[].ResourceARN' \
  --output table

echo
echo "=== MTD cost for Project=${PROJECT} (requires activated cost tags + ~24h lag) ==="
START=$(date -u +%Y-%m-01)
END=$(date -u +%Y-%m-%d)
aws ce get-cost-and-usage \
  --time-period Start=$START,End=$END \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter '{"Tags":{"Key":"Project","Values":["'${PROJECT}'"]}}' \
  --query 'ResultsByTime[0].Total.UnblendedCost' 2>&1 || echo "  (tag not yet active or Cost Explorer not ready)"

#!/usr/bin/env bash
# Submit one MotionCor2 job. Polls until SUCCEEDED or FAILED, prints timings + log tail + cost estimate.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

# Windows git-bash only ships `python`; Linux ships `python3`. Pick whichever exists.
PY="$(command -v python3 || command -v python)"
[ -z "$PY" ] && { echo "ERROR: no python interpreter found" >&2; exit 1; }

QUEUE_NAME="${PROJECT}-queue"
JD_NAME="${PROJECT}-motioncor"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
JOB_ID="batch-${TIMESTAMP}"

INPUT_S3="s3://${S3_TEST_BUCKET}/${S3_DATA_PREFIX}/20241203_54530_integrated_movie.mrc.tif"
OUTPUT_S3="s3://${S3_WORK_BUCKET}/test-1-batch/"

read -r -d '' OVERRIDES <<EOF || true
{
  "environment": [
    {"name": "MOTIONCOR_INPUT_S3",      "value": "${INPUT_S3}"},
    {"name": "MOTIONCOR_OUTPUT_PREFIX", "value": "${OUTPUT_S3}"},
    {"name": "MOTIONCOR_JOB_ID",        "value": "${JOB_ID}"}
  ]
}
EOF

echo "Submitting ${JOB_ID}..."
AWS_JOB_ID=$(aws batch submit-job \
  --job-name "$JOB_ID" \
  --job-queue "$QUEUE_NAME" \
  --job-definition "$JD_NAME" \
  --container-overrides "$OVERRIDES" \
  --tags "Project=${PROJECT},Owner=${OWNER},CostCenter=${COST_CENTER},JobId=${JOB_ID}" \
  --query 'jobId' --output text)
echo "Submitted: $AWS_JOB_ID"

PREV_STATUS=""
START_T=$(date +%s)
while true; do
  J=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0].[status,statusReason,createdAt,startedAt,stoppedAt]' --output text)
  STATUS=$(echo "$J" | cut -f1)
  if [ "$STATUS" != "$PREV_STATUS" ]; then
    printf "%6ds  %s  %s\n" "$(( $(date +%s) - START_T ))" "$STATUS" "$(echo "$J" | cut -f2)"
    PREV_STATUS="$STATUS"
  fi
  case "$STATUS" in
    SUCCEEDED|FAILED) break ;;
  esac
  sleep 10
done

echo
echo "=== Final ==="
aws batch describe-jobs --jobs "$AWS_JOB_ID" \
  --query 'jobs[0].{status:status,reason:statusReason,createdAt:createdAt,startedAt:startedAt,stoppedAt:stoppedAt,logStream:container.logStreamName,exitCode:container.exitCode}'

# Timings
J=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0]')
"$PY" - <<PY
import json
j = json.loads('''$J''')
c = j.get("createdAt", 0) / 1000
s = j.get("startedAt", 0) / 1000
e = j.get("stoppedAt", 0) / 1000
print()
print("=== Timings ===")
print(f"  submit -> start (provision+pull): {s-c:8.1f}s")
print(f"  start  -> stop  (run time):       {e-s:8.1f}s")
print(f"  total  wall time:                 {e-c:8.1f}s")
print()
print("=== Rough cost (spot ~\$0.158/hr x run time only) ===")
print(f"  \${(e-s) * 0.158 / 3600:.4f}  (actual = whole instance lifecycle, could be ~2x for boot/teardown)")
PY

# Log tail
STREAM=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0].container.logStreamName' --output text)
if [ -n "$STREAM" ] && [ "$STREAM" != "None" ]; then
  echo
  echo "=== Log tail (last 30) ==="
  aws logs get-log-events --log-group-name /aws/batch/job --log-stream-name "$STREAM" \
    --limit 30 --start-from-head --query 'events[].message' --output text
fi

echo
echo "=== Output listing ==="
aws s3 ls "${OUTPUT_S3}${JOB_ID}/" --recursive --human-readable || echo "  (no outputs uploaded — check logs)"

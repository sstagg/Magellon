#!/usr/bin/env bash
# Attach to an already-submitted Batch job and report timings/cost/logs.
#   usage: bash poll-existing.sh <aws-job-id> [<job-tag-for-s3-path>]
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh" >/dev/null

PY="$(command -v python3 || command -v python)"
[ -z "$PY" ] && { echo "ERROR: no python interpreter" >&2; exit 1; }

AWS_JOB_ID="${1:?usage: poll-existing.sh <aws-job-id> [<tag>]}"
JOB_TAG="${2:-}"

PREV=""
START=$(date +%s)
while true; do
  J=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0].[status,statusReason]' --output text)
  STATUS=$(echo "$J" | cut -f1)
  REASON=$(echo "$J" | cut -f2)
  if [ "$STATUS" != "$PREV" ]; then
    printf "%6ds  %-12s  %s\n" "$(( $(date +%s) - START ))" "$STATUS" "$REASON"
    PREV="$STATUS"
  fi
  case "$STATUS" in SUCCEEDED|FAILED) break ;; esac
  sleep 10
done

echo
echo "=== Final ==="
aws batch describe-jobs --jobs "$AWS_JOB_ID" \
  --query 'jobs[0].{status:status,reason:statusReason,exitCode:container.exitCode,logStream:container.logStreamName}' \
  --output table

echo
echo "=== Timings + rough cost ==="
J_FULL=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0]')
"$PY" -c "
import json, sys
j = json.loads(sys.argv[1])
c = j.get('createdAt', 0)/1000
s = j.get('startedAt', 0)/1000
e = j.get('stoppedAt', 0)/1000
print(f'  submit -> start (provision+pull): {s-c:8.1f}s')
print(f'  start  -> stop  (run time):       {e-s:8.1f}s')
print(f'  total  wall time:                 {e-c:8.1f}s')
cost = (e-s) * 0.158 / 3600
print(f'  rough cost (run-time only @ \$0.158/hr spot): \${cost:.4f}')
print('  (actual billing = whole instance lifecycle, typically ~2x for boot/teardown)')
" "$J_FULL"

STREAM=$(aws batch describe-jobs --jobs "$AWS_JOB_ID" --query 'jobs[0].container.logStreamName' --output text)
if [ -n "$STREAM" ] && [ "$STREAM" != "None" ]; then
  echo
  echo "=== Log tail (last 40) ==="
  aws logs get-log-events --log-group-name /aws/batch/job --log-stream-name "$STREAM" \
    --limit 40 --start-from-head --query 'events[].message' --output text
fi

if [ -n "$JOB_TAG" ]; then
  echo
  echo "=== Output listing (s3://${S3_WORK_BUCKET}/test-1-batch/${JOB_TAG}/) ==="
  aws s3 ls "s3://${S3_WORK_BUCKET}/test-1-batch/${JOB_TAG}/" --recursive --human-readable 2>&1 || echo "  (no outputs)"
fi

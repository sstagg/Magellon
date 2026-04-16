#!/usr/bin/env bash
# Wait until RabbitMQ + plugin are healthy and the consumer is attached.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

source "${SCRIPT_DIR}/.instance-env"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY_FILE ec2-user@$PUBLIC_IP"

echo "=== Waiting for compose services ==="
for i in $(seq 1 36); do  # 6 min
  STATUS=$($SSH 'cd /home/ec2-user/magellon && docker compose ps --format json 2>/dev/null' || echo '[]')
  HEALTHY=$(echo "$STATUS" | python -c "
import sys,json
try:
    svcs = json.loads(sys.stdin.read())
    if isinstance(svcs, dict): svcs = [svcs]
    up = sum(1 for s in svcs if 'running' in s.get('State','').lower())
    print(up)
except: print(0)
" 2>/dev/null || echo 0)
  echo "  attempt ${i}: ${HEALTHY} services running"
  [ "$HEALTHY" -ge 2 ] && break
  sleep 10
done

echo
echo "=== Plugin logs (tail) ==="
$SSH 'cd /home/ec2-user/magellon && docker compose logs --tail=30 motioncor 2>&1' || true

echo
echo "=== Checking RabbitMQ consumer ==="
for i in $(seq 1 12); do  # 2 min
  CONSUMERS=$($SSH "curl -s -u rabbit:behd1d2 http://localhost:15672/api/queues/%2F/motioncor_tasks_queue 2>/dev/null" \
    | python -c "import sys,json; print(json.load(sys.stdin).get('consumers',0))" 2>/dev/null || echo 0)
  echo "  consumers on motioncor_tasks_queue: $CONSUMERS"
  [ "$CONSUMERS" -ge 1 ] && break
  sleep 10
done

echo
echo "=== Pre-declaring debug_queue ==="
$SSH 'curl -s -u rabbit:behd1d2 -X PUT \
  -H "content-type:application/json" \
  -d "{\"durable\":true}" \
  http://localhost:15672/api/queues/%2F/debug_queue' || true

if [ "$CONSUMERS" -ge 1 ]; then
  echo
  echo "Ready. Next: ./03-run-test.sh"
else
  echo
  echo "WARNING: no consumer detected. Check plugin logs:"
  echo "  $SSH 'cd /home/ec2-user/magellon && docker compose logs motioncor'"
  exit 1
fi

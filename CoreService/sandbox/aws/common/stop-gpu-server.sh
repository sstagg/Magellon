#!/usr/bin/env bash
# Stop magellon-gpu-server (i-059b91233e481b50a). EBS + EIP persist, IP unchanged on next start.
# Stopped cost ~$12/mo; running ~$384/mo.
# Usage: common/stop-gpu-server.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

INSTANCE_ID="i-059b91233e481b50a"
echo "Stopping $INSTANCE_ID..."
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --query 'StoppingInstances[0].{Id:InstanceId,Prev:PreviousState.Name,Curr:CurrentState.Name}'
echo "Stop signalled. Takes 30-90s to finalize."

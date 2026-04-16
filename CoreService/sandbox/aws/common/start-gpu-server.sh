#!/usr/bin/env bash
# Start magellon-gpu-server (i-059b91233e481b50a). EIP 34.235.206.46 reattaches automatically.
# Usage: common/start-gpu-server.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

INSTANCE_ID="i-059b91233e481b50a"
echo "Starting $INSTANCE_ID..."
aws ec2 start-instances --instance-ids "$INSTANCE_ID" --query 'StartingInstances[0].{Id:InstanceId,Prev:PreviousState.Name,Curr:CurrentState.Name}'

echo "Waiting for running state (usually ~30s)..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Running. Public IP: $IP  (should be 34.235.206.46)"
echo "SSH: ssh -i <magellon_test.pem> ec2-user@$IP  (or ubuntu@$IP — depends on AMI)"

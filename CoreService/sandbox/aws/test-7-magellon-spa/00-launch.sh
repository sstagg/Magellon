#!/usr/bin/env bash
# Launch a c5.4xlarge on-demand instance for the magellon-spa test drive.
# CPU-only — our Rust SPA path doesn't have a CUDA backend yet.
# User-data installs the Rust toolchain + git so 02-build can build
# magellon-rust-mrc directly on the instance.
# Writes .instance-env for subsequent scripts.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

SG_NAME="${PROJECT}-magellon-spa-sg"
KEY_NAME="${PROJECT}-magellon-spa-key"
KEY_FILE="$HOME/.ssh/${KEY_NAME}.pem"
ENV_FILE="${SCRIPT_DIR}/.instance-env"

MY_IP=$(curl -4s https://checkip.amazonaws.com | tr -d '\r\n')
echo "My IP: ${MY_IP}"

# Plain Ubuntu 22.04 LTS — no DLAMI overhead since we don't need CUDA.
AMI_ID=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
              "Name=state,Values=available" \
              "Name=architecture,Values=x86_64" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
echo "AMI: ${AMI_ID}"

if [ ! -f "$KEY_FILE" ]; then
  aws ec2 delete-key-pair --key-name "$KEY_NAME" 2>/dev/null || true
  aws ec2 create-key-pair --key-name "$KEY_NAME" --query 'KeyMaterial' --output text > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  echo "Created key pair ${KEY_NAME} → ${KEY_FILE}"
else
  echo "Key file exists: ${KEY_FILE}"
fi

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "Creating SG ${SG_NAME}..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "SSH from my IP for ${PROJECT} magellon-spa test" \
    --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" \
    --query GroupId --output text)
fi
echo "SG: ${SG_ID}"

aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
  --protocol tcp --port 22 --cidr "${MY_IP}/32" 2>/dev/null || true

SUBNET_ID=$(echo "$SUBNETS" | tr ',' '\n' | head -1)

USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -uxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data -s) 2>&1

export DEBIAN_FRONTEND=noninteractive
echo "=== installing build deps ==="
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential pkg-config curl wget unzip git \
  libssl-dev libfftw3-dev

echo "=== installing Rust toolchain for ubuntu user ==="
# Install only as the ubuntu user — non-interactive SSH sessions log
# in as ubuntu, and /root/.cargo/bin is unreadable to non-root because
# /root has mode 700. Symlink ubuntu's install into /usr/local/bin so
# every ssh session can find cargo without a PATH dance.
sudo -u ubuntu bash -c "
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain stable --no-modify-path
"
ln -sf /home/ubuntu/.cargo/bin/cargo  /usr/local/bin/cargo
ln -sf /home/ubuntu/.cargo/bin/rustc  /usr/local/bin/rustc
ln -sf /home/ubuntu/.cargo/bin/rustup /usr/local/bin/rustup

echo "=== rust toolchain ==="
/usr/local/bin/rustc --version
/usr/local/bin/cargo --version

echo "=== creating data directories ==="
mkdir -p /data /work /src
chown -R ubuntu:ubuntu /data /work /src

echo "=== user-data done ==="
USERDATA
)

# c5.4xlarge — 16 vCPU, 32 GB RAM, no GPU. Our SPA code is CPU-only.
echo "Launching c5.4xlarge on-demand..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type c5.4xlarge \
  --count 1 \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --key-name "$KEY_NAME" \
  --associate-public-ip-address \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=60,VolumeType=gp3,DeleteOnTermination=true}' \
  --user-data "$USER_DATA" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}},{Key=Name,Value=${PROJECT}-magellon-spa-test},{Key=Purpose,Value=magellon-spa-test-drive}]" \
    "ResourceType=volume,Tags=${TAGS_SHORT}" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance: ${INSTANCE_ID}"

echo "Waiting for running state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Public IP: ${PUBLIC_IP}"

cat > "$ENV_FILE" <<EOF
INSTANCE_ID=${INSTANCE_ID}
PUBLIC_IP=${PUBLIC_IP}
SG_ID=${SG_ID}
KEY_FILE=${KEY_FILE}
KEY_NAME=${KEY_NAME}
EOF
echo "Wrote ${ENV_FILE}"

echo "Waiting for SSH..."
for i in $(seq 1 30); do
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" 'echo OK' 2>/dev/null && break
  echo "  attempt $i..."
  sleep 10
done

echo "Waiting for user-data (Rust install ~3 min)..."
for i in $(seq 1 40); do
  STATUS=$(ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
    'if [ -x /usr/local/bin/cargo ]; then echo READY; else echo BUILDING; fi' 2>/dev/null || echo SSH_FAIL)
  if [ "$STATUS" = "READY" ]; then
    echo "Rust toolchain installed (attempt $i)"
    break
  fi
  echo "  poll $i: $STATUS"
  sleep 15
done

echo
echo "=== Instance ready ==="
echo "  ssh -i ${KEY_FILE} ubuntu@${PUBLIC_IP}"
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
  '/usr/local/bin/cargo --version 2>&1 | head -2' || true
echo
echo "Next: ./01-fetch-data.sh && ./02-build-magellon.sh"

#!/usr/bin/env bash
# Launch a g5.2xlarge on-demand instance for the RELION 5 test drive.
# User-data installs CUDA toolkit (already on DLAMI), nvidia-container-toolkit,
# Docker, and builds RELION 5.0 from source under /opt/relion.
# Writes .instance-env for subsequent scripts.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

SG_NAME="${PROJECT}-relion-sg"
KEY_NAME="${PROJECT}-relion-key"
KEY_FILE="$HOME/.ssh/${KEY_NAME}.pem"
ENV_FILE="${SCRIPT_DIR}/.instance-env"

# --- My public IP for SSH ingress ---
MY_IP=$(curl -4s https://checkip.amazonaws.com | tr -d '\r\n')
echo "My IP: ${MY_IP}"

# --- AMI: Deep Learning OSS Nvidia Driver AMI (Ubuntu 22.04). Has CUDA, drivers,
# Docker, nvidia-container-toolkit pre-installed → saves ~10 min.
AMI_ID=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.4* (Ubuntu 22.04)*" \
              "Name=state,Values=available" \
              "Name=architecture,Values=x86_64" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
if [ -z "$AMI_ID" ] || [ "$AMI_ID" = "None" ]; then
  # Fallback: any current Deep Learning Ubuntu AMI.
  AMI_ID=$(aws ec2 describe-images --owners amazon \
      --filters "Name=name,Values=Deep Learning*Ubuntu 22.04*" \
                "Name=state,Values=available" \
                "Name=architecture,Values=x86_64" \
      --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
fi
echo "AMI: ${AMI_ID}"

# --- Key pair ---
if [ ! -f "$KEY_FILE" ]; then
  aws ec2 delete-key-pair --key-name "$KEY_NAME" 2>/dev/null || true
  aws ec2 create-key-pair --key-name "$KEY_NAME" --query 'KeyMaterial' --output text > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  echo "Created key pair ${KEY_NAME} → ${KEY_FILE}"
else
  echo "Key file exists: ${KEY_FILE}"
fi

# --- Security group ---
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "Creating SG ${SG_NAME}..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "SSH from my IP for ${PROJECT} RELION test" \
    --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" \
    --query GroupId --output text)
fi
echo "SG: ${SG_ID}"

aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
  --protocol tcp --port 22 --cidr "${MY_IP}/32" 2>/dev/null || true

SUBNET_ID=$(echo "$SUBNETS" | tr ',' '\n' | head -1)

# --- User data ---
USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -uxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data -s) 2>&1

export DEBIAN_FRONTEND=noninteractive
echo "=== installing RELION build deps ==="
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential cmake git pkg-config \
  libfftw3-dev libtiff-dev libpng-dev libfltk1.3-dev \
  libxext-dev libxft-dev libxinerama-dev libxcursor-dev libxrandr-dev libxi-dev \
  openmpi-bin libopenmpi-dev \
  curl wget unzip rsync

echo "=== building RELION 5.0 from source ==="
cd /opt
git clone --depth 1 --branch ver5.0 https://github.com/3dem/relion.git
mkdir -p relion/build && cd relion/build

# A10G is sm_86 (Ampere). Force the arch so cmake doesn't probe.
cmake -DCUDA=ON -DCUDA_ARCH=86 \
      -DCMAKE_INSTALL_PREFIX=/opt/relion \
      -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc) 2>&1 | tail -200
make install
ln -sf /opt/relion/bin/* /usr/local/bin/

echo "=== RELION binaries installed ==="
ls /opt/relion/bin | head -20

echo "=== creating data directories ==="
mkdir -p /data /work
chown -R ubuntu:ubuntu /data /work

echo "=== user-data done ==="
USERDATA
)

# --- Launch on-demand g5.2xlarge ---
echo "Launching g5.2xlarge on-demand..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type g5.2xlarge \
  --count 1 \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --key-name "$KEY_NAME" \
  --associate-public-ip-address \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=80,VolumeType=gp3,DeleteOnTermination=true}' \
  --user-data "$USER_DATA" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}},{Key=Name,Value=${PROJECT}-relion-test},{Key=Purpose,Value=relion-test-drive}]" \
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

echo "Waiting for user-data (RELION compile takes ~20 min)..."
for i in $(seq 1 60); do
  DONE=$(ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
    'sudo grep -c "user-data done" /var/log/user-data.log 2>/dev/null || echo 0')
  [ "$DONE" != "0" ] && break
  echo "  build still running (attempt $i)..."
  sleep 30
done

echo
echo "=== Instance ready ==="
echo "  ssh -i ${KEY_FILE} ubuntu@${PUBLIC_IP}"
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$PUBLIC_IP" \
  '/opt/relion/bin/relion_refine --version 2>&1 | head -5' || true
echo
echo "Next: ./01-fetch-data.sh"

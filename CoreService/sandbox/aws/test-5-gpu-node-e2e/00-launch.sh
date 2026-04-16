#!/usr/bin/env bash
# Launch a g4dn.2xlarge spot instance for the plugin end-to-end test.
# Creates: SG (ingress 22,5672,15672 from your IP), EC2 key pair, spot instance.
# Writes instance metadata to .instance-env for subsequent scripts.

set -euo pipefail
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MY_DIR="$SCRIPT_DIR"
source "${SCRIPT_DIR}/../common/activate.sh"
SCRIPT_DIR="$MY_DIR"

SG_NAME="${PROJECT}-e2e-sg"
KEY_NAME="${PROJECT}-e2e-key"
KEY_FILE="$HOME/.ssh/${KEY_NAME}.pem"
ENV_FILE="${SCRIPT_DIR}/.instance-env"

# --- My public IP ---
MY_IP=$(curl -4s https://checkip.amazonaws.com | tr -d '\r\n')
echo "My IP: ${MY_IP}"

# --- ECS-GPU AMI ---
AMI_ID=$(aws ec2 describe-images --owners amazon \
    --filters "Name=name,Values=amzn2-ami-ecs-gpu-hvm-*" "Name=state,Values=available" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
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
    --description "SSH + RabbitMQ for ${PROJECT} e2e test" \
    --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=${TAGS_SHORT}" \
    --query GroupId --output text)
fi
echo "SG: ${SG_ID}"

# Ingress: SSH + AMQP + RMQ management from my IP only
for PORT in 22 5672 15672; do
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port $PORT --cidr "${MY_IP}/32" 2>/dev/null || true
done

SUBNET_ID=$(echo "$SUBNETS" | tr ',' '\n' | head -1)

# --- User data ---
USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -uxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data -s) 2>&1

yum install -y unzip rsync || true

# Install AWS CLI v2 (AL2 ECS-GPU AMI doesn't include it)
if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  (cd /tmp && unzip -q awscliv2.zip && ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli)
fi
export PATH=/usr/local/bin:$PATH

# Docker compose v2 plugin (ECS AMI ships Docker but not the compose plugin)
DOCKER_CLI_PLUGINS=${DOCKER_CLI_PLUGINS:-/usr/local/lib/docker/cli-plugins}
if ! docker compose version >/dev/null 2>&1; then
  mkdir -p "$DOCKER_CLI_PLUGINS"
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.1/docker-compose-linux-x86_64" -o "${DOCKER_CLI_PLUGINS}/docker-compose"
  chmod +x "${DOCKER_CLI_PLUGINS}/docker-compose"
fi

# NVIDIA sanity check
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi || echo "GPU sanity FAILED"

# Prep directories (ec2-user writable)
mkdir -p /data /jobs
chown ec2-user:ec2-user /data /jobs

echo "=== user-data done ==="
USERDATA
)

# --- Launch spot ---
echo "Requesting spot g4dn.2xlarge..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type g4dn.2xlarge \
  --count 1 \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --key-name "$KEY_NAME" \
  --iam-instance-profile "Name=${ROLE_BATCH_INSTANCE}" \
  --associate-public-ip-address \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=60,VolumeType=gp3,DeleteOnTermination=true}' \
  --instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}' \
  --user-data "$USER_DATA" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}},{Key=Name,Value=${PROJECT}-e2e-gpu},{Key=Purpose,Value=plugin-e2e-test}]" \
    "ResourceType=volume,Tags=${TAGS_SHORT}" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance: ${INSTANCE_ID}"

# --- Wait for running + public IP ---
echo "Waiting for running state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Public IP: ${PUBLIC_IP}"

# --- Save for other scripts ---
cat > "$ENV_FILE" <<EOF
INSTANCE_ID=${INSTANCE_ID}
PUBLIC_IP=${PUBLIC_IP}
SG_ID=${SG_ID}
KEY_FILE=${KEY_FILE}
KEY_NAME=${KEY_NAME}
EOF
echo "Wrote ${ENV_FILE}"

# --- Wait for SSH ---
echo "Waiting for SSH..."
for i in $(seq 1 30); do
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY_FILE" ec2-user@"$PUBLIC_IP" 'echo OK' 2>/dev/null && break
  echo "  attempt $i..."
  sleep 10
done

# --- Wait for user-data to finish ---
echo "Waiting for user-data to complete..."
for i in $(seq 1 30); do
  DONE=$(ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ec2-user@"$PUBLIC_IP" \
    'grep -c "user-data done" /var/log/user-data.log 2>/dev/null || echo 0')
  [ "$DONE" != "0" ] && break
  echo "  cloud-init still running (attempt $i)..."
  sleep 10
done

echo
echo "Instance ready."
echo "  ssh -i ${KEY_FILE} ec2-user@${PUBLIC_IP}"
echo "  Next: ./01-deploy.sh"

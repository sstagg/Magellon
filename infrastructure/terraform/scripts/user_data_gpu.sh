#!/bin/bash
# Bootstrap script for the GPU instance (MotionCor plugin only).
# Runs once at first boot via EC2 user-data (Deep Learning AMI base).
# NVIDIA drivers are pre-installed in the DLAMI — no driver install needed.
set -euo pipefail

LOG=/var/log/magellon-gpu-bootstrap.log
exec > >(tee -a $LOG) 2>&1
echo "=== Magellon GPU bootstrap started $(date) ==="

# ── Template variables (injected by Terraform templatefile()) ─────────────────
EFS_ID="${efs_id}"
AWS_REGION="${aws_region}"
SECRET_ARN="${secret_arn}"
MAIN_PRIVATE_IP="${main_private_ip}"
RABBITMQ_USER="${rabbitmq_user}"
CUDA_IMAGE="${cuda_image}"
MOTIONCOR_BINARY="${motioncor_binary}"

# ── System packages ───────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y nfs-common amazon-efs-utils jq awscli

# ── Docker Compose plugin (DLAMI has Docker but may lack compose v2) ──────────
apt-get install -y docker-compose-plugin 2>/dev/null || \
  curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose

systemctl enable docker
systemctl start docker

# ── NVIDIA Container Toolkit (ensure GPU access from Docker) ─────────────────
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor \
  -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L "https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list" | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update -y
apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# ── Verify GPU ────────────────────────────────────────────────────────────────
nvidia-smi || { echo "ERROR: nvidia-smi failed — GPU not available"; exit 1; }

# ── Mount EFS ─────────────────────────────────────────────────────────────────
mkdir -p /mnt/efs
mount -t efs -o tls,iam "$EFS_ID":/ /mnt/efs
echo "$EFS_ID:/ /mnt/efs efs _netdev,tls,iam 0 0" >> /etc/fstab

# ── Fetch secrets ─────────────────────────────────────────────────────────────
SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)

RABBITMQ_PASSWORD=$(echo "$SECRETS"  | jq -r .RABBITMQ_DEFAULT_PASS)
DRAGONFLY_PASSWORD=$(echo "$SECRETS" | jq -r .DRAGONFLY_PASSWORD)

# ── Write .env ────────────────────────────────────────────────────────────────
MAGELLON_DIR=/opt/magellon-gpu
mkdir -p "$MAGELLON_DIR"

cat > "$MAGELLON_DIR/.env" <<EOF
# GPU instance .env – all broker/cache hosts point to main instance private IP

MAGELLON_HOME_PATH=/mnt/efs/magellon
MAGELLON_GPFS_PATH=/mnt/efs/gpfs
MAGELLON_JOBS_PATH=/mnt/efs/jobs

# Main instance connectivity
RABBITMQ_HOST=$MAIN_PRIVATE_IP
RABBITMQ_PORT=5672
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD
DRAGONFLY_HOST=$MAIN_PRIVATE_IP
DRAGONFLY_PORT=6379
DRAGONFLY_PASSWORD=$DRAGONFLY_PASSWORD
NATS_URL=nats://$MAIN_PRIVATE_IP:4222

# MotionCor specifics
CUDA_IMAGE=$CUDA_IMAGE
MOTIONCOR_BINARY=$MOTIONCOR_BINARY

MAGELLON_MOTIONCOR_PLUGIN_PORT=8036
APP_ENV=production
RUN_ENV=docker
EOF
chmod 600 "$MAGELLON_DIR/.env"

# ── Write SDK settings override for RabbitMQ (SDK reads YAML, not env vars) ──
# The magellon SDK BaseAppSettings reads a settings_prod.yml when RUN_ENV=docker.
# We mount this override file into the container at the expected path.
cat > "$MAGELLON_DIR/settings_prod.yml" <<EOF
rabbitmq:
  host_name: $MAIN_PRIVATE_IP
  port: 5672
  user_name: $RABBITMQ_USER
  password: $RABBITMQ_PASSWORD
  virtual_host: /

nats:
  url: nats://$MAIN_PRIVATE_IP:4222

dragonfly:
  host: $MAIN_PRIVATE_IP
  port: 6379
  password: $DRAGONFLY_PASSWORD
EOF
chmod 600 "$MAGELLON_DIR/settings_prod.yml"

# ── Pull docker-compose.gpu.yml ──────────────────────────────────────────────
# Source: Docker/AWS_docker_compose/docker-compose.gpu.yml in the repo.
# aws s3 cp s3://magellon-terraform-state/config/docker-compose.gpu.yml ./docker-compose.gpu.yml

# ── Systemd service ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/magellon-gpu.service <<'UNIT'
[Unit]
Description=Magellon GPU Worker (MotionCor Plugin)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/magellon-gpu
EnvironmentFile=/opt/magellon-gpu/.env
ExecStart=/usr/bin/docker compose -f docker-compose.gpu.yml up -d --pull always
ExecStop=/usr/bin/docker compose -f docker-compose.gpu.yml down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable magellon-gpu.service

echo "=== GPU bootstrap complete $(date). GPU worker will start once compose file is deployed. ==="

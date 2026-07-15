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
AP_MAGELLON="${ap_magellon_id}"
AP_GPFS="${ap_gpfs_id}"
AP_JOBS="${ap_jobs_id}"
AWS_REGION="${aws_region}"
SECRET_ARN="${secret_arn}"
RABBITMQ_USER="${rabbitmq_user}"
CUDA_IMAGE="${cuda_image}"
MOTIONCOR_BINARY="${motioncor_binary}"
REPO_BRANCH="${repo_branch}"

# Broker hosts are resolved via Route 53 private hosted zone (magellon.internal).
# When the main EC2 is replaced, only the DNS A record changes — this file
# stays the same on every GPU instance, allowing unlimited horizontal scaling.
RABBITMQ_HOST="rabbitmq.magellon.internal"
NATS_HOST="nats.magellon.internal"
DRAGONFLY_HOST="dragonfly.magellon.internal"

REPO_URL="https://github.com/sstagg/Magellon.git"
REPO_DIR=/opt/magellon-repo
MAGELLON_DIR=/opt/magellon-gpu

# ── System packages ───────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y nfs-common jq awscli git

# ── Docker + NVIDIA runtime (DLAMI pre-installs both) ────────────────────────
# Upgrade compose plugin if a newer version is available; fall back to
# standalone binary only if the plugin is completely absent.
apt-get install -y docker-compose-plugin 2>/dev/null || true

# DLAMI pre-configures nvidia-container-runtime. Re-run configure to ensure
# /etc/docker/daemon.json has the correct runtime entry, then restart Docker.
nvidia-ctk runtime configure --runtime=docker 2>/dev/null || true
systemctl enable docker
systemctl restart docker
sleep 5

# ── Verify GPU ────────────────────────────────────────────────────────────────
nvidia-smi || { echo "ERROR: nvidia-smi failed — GPU not available"; exit 1; }

# ── Mount EFS via NFS4 ────────────────────────────────────────────────────────
mkdir -p /mnt/efs
EFS_DNS="$EFS_ID.efs.$AWS_REGION.amazonaws.com"
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport \
  "$EFS_DNS":/ /mnt/efs
echo "$EFS_DNS:/ /mnt/efs nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0" >> /etc/fstab

mkdir -p /mnt/efs/magellon /mnt/efs/gpfs /mnt/efs/jobs
chmod 777 /mnt/efs/magellon /mnt/efs/gpfs /mnt/efs/jobs

# ── Clone application repository ──────────────────────────────────────────────
git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"

# ── Fetch secrets ─────────────────────────────────────────────────────────────
SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)

RABBITMQ_PASSWORD=$(echo "$SECRETS"  | jq -r .RABBITMQ_DEFAULT_PASS)
DRAGONFLY_PASSWORD=$(echo "$SECRETS" | jq -r .DRAGONFLY_PASSWORD)

# ── Resolve broker IP at boot via explicit VPC DNS query ──────────────────────
# Docker containers cannot resolve *.magellon.internal because systemd-resolved
# only routes *.ec2.internal to 10.0.0.2. Resolve once at boot and embed the
# IP directly in configs so no container-level DNS is required.
BROKER_IP=$(dig @10.0.0.2 +short rabbitmq.magellon.internal | tail -1)
if [ -z "$BROKER_IP" ]; then
  echo "ERROR: Could not resolve rabbitmq.magellon.internal via VPC DNS — main EC2 not up yet?"
  exit 1
fi
echo "Broker IP resolved to $BROKER_IP"

# ── Write .env ────────────────────────────────────────────────────────────────
mkdir -p "$MAGELLON_DIR"

cat > "$MAGELLON_DIR/.env" <<EOF
MAGELLON_HOME_PATH=/mnt/efs/magellon
MAGELLON_GPFS_PATH=/mnt/efs/gpfs
MAGELLON_JOBS_PATH=/mnt/efs/jobs

# Broker connectivity — IP resolved at boot from Route 53 private zone
RABBITMQ_HOST=$BROKER_IP
RABBITMQ_PORT=5672
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD
DRAGONFLY_HOST=$BROKER_IP
DRAGONFLY_PORT=6379
DRAGONFLY_PASSWORD=$DRAGONFLY_PASSWORD
NATS_URL=nats://$BROKER_IP:4222

# MotionCor
CUDA_IMAGE=$CUDA_IMAGE
MOTIONCOR_BINARY=$MOTIONCOR_BINARY

MAGELLON_MOTIONCOR_PLUGIN_PORT=8036
APP_ENV=production
RUN_ENV=docker
AWS_REGION=$AWS_REGION
EOF
chmod 600 "$MAGELLON_DIR/.env"

# ── Write SDK settings override (mounted into container at /app/settings_prod.yml)
cat > "$MAGELLON_DIR/settings_prod.yml" <<EOF
ENV_TYPE: production
LOCAL_IP_ADDRESS: magellon_motioncor_plugin_container
PORT_NUMBER: 8000

MAGELLON_GPFS_PATH: /gpfs
HOST_GPFS_PATH: /gpfs
JOBS_DIR: /jobs
HOST_JOBS_DIR: /jobs

rabbitmq_settings:
  HOST_NAME: $BROKER_IP
  PORT: 5672
  USER_NAME: $RABBITMQ_USER
  PASSWORD: $RABBITMQ_PASSWORD
  VIRTUAL_HOST: /
  SSL_ENABLED: false
  CONNECTION_TIMEOUT: 30
  PREFETCH_COUNT: 10
  QUEUE_NAME: motioncor_tasks_queue
  OUT_QUEUE_NAME: motioncor_out_tasks_queue
EOF
chmod 600 "$MAGELLON_DIR/settings_prod.yml"

# ── Systemd service ───────────────────────────────────────────────────────────
# Uses the compose file from the cloned repo; .env provides runtime secrets.
cat > /etc/systemd/system/magellon-gpu.service <<'UNIT'
[Unit]
Description=Magellon GPU Worker (MotionCor Plugin)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/magellon-repo
EnvironmentFile=/opt/magellon-gpu/.env
ExecStart=/usr/bin/docker compose \
  -f Docker/AWS_docker_compose/docker-compose.gpu.yml \
  --env-file /opt/magellon-gpu/.env \
  up -d --build
ExecStop=/usr/bin/docker compose \
  -f Docker/AWS_docker_compose/docker-compose.gpu.yml \
  down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable magellon-gpu.service
systemctl start magellon-gpu.service

echo "=== GPU bootstrap complete $(date). Check 'journalctl -u magellon-gpu.service' for status. ==="

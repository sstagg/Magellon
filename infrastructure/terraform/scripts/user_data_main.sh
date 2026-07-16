#!/bin/bash
# Bootstrap script for the MAIN CPU instance.
# Runs once at first boot via EC2 user-data.
set -euo pipefail

LOG=/var/log/magellon-bootstrap.log
exec > >(tee -a $LOG) 2>&1
echo "=== Magellon main bootstrap started $(date) ==="

# ── Template variables (injected by Terraform templatefile()) ─────────────────
EFS_ID="${efs_id}"
AP_MAGELLON="${ap_magellon_id}"
AP_GPFS="${ap_gpfs_id}"
AP_JOBS="${ap_jobs_id}"
AWS_REGION="${aws_region}"
SECRET_ARN="${secret_arn}"
MYSQL_DATABASE="${mysql_database}"
MYSQL_USER="${mysql_user}"
RABBITMQ_USER="${rabbitmq_user}"
GRAFANA_USER="${grafana_user}"
REPO_BRANCH="${repo_branch}"

REPO_URL="https://github.com/sstagg/Magellon.git"
REPO_DIR=/opt/magellon-repo
MAGELLON_DIR=/opt/magellon

# ── System updates ────────────────────────────────────────────────────────────
apt-get update -y
# nfs-common provides NFS4 support (replaces amazon-efs-utils which isn't in Ubuntu repos)
apt-get install -y \
  apt-transport-https ca-certificates curl gnupg lsb-release \
  nfs-common jq awscli unzip git openssl

# ── CloudWatch Agent ──────────────────────────────────────────────────────────
wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c ssm:/AmazonCloudWatch-Config 2>/dev/null || true

# ── Docker ────────────────────────────────────────────────────────────────────
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

# ── Mount EFS via NFS4 (nfs-common installed above, no extra packages needed) ─
mkdir -p /mnt/efs
EFS_DNS="$EFS_ID.efs.$AWS_REGION.amazonaws.com"
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport \
  "$EFS_DNS":/ /mnt/efs
echo "$EFS_DNS:/ /mnt/efs nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0" >> /etc/fstab

mkdir -p /mnt/efs/magellon /mnt/efs/gpfs /mnt/efs/jobs
chmod 777 /mnt/efs/magellon /mnt/efs/gpfs /mnt/efs/jobs

# ── Clone application repository ──────────────────────────────────────────────
git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"

# ── Set up service config files ───────────────────────────────────────────────
mkdir -p "$MAGELLON_DIR/services/mysql/"{data,conf,init}
mkdir -p "$MAGELLON_DIR/services/prometheus"

cp "$REPO_DIR/Docker/services/mysql/init/magellon01db.sql" \
   "$MAGELLON_DIR/services/mysql/init/" 2>/dev/null || true
cp "$REPO_DIR/Docker/services/prometheus/prometheus.yml" \
   "$MAGELLON_DIR/services/prometheus/" 2>/dev/null || true

# ── Fetch secrets from Secrets Manager ───────────────────────────────────────
SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)

MYSQL_ROOT_PASSWORD=$(echo "$SECRETS" | jq -r .MYSQL_ROOT_PASSWORD)
MYSQL_PASSWORD=$(echo "$SECRETS"      | jq -r .MYSQL_PASSWORD)
RABBITMQ_PASSWORD=$(echo "$SECRETS"   | jq -r .RABBITMQ_DEFAULT_PASS)
DRAGONFLY_PASSWORD=$(echo "$SECRETS"  | jq -r .DRAGONFLY_PASSWORD)
GRAFANA_PASSWORD=$(echo "$SECRETS"    | jq -r .GRAFANA_USER_PASS)

# ── Generate a fresh JWT secret for this deployment ───────────────────────────
JWT_SECRET_KEY=$(openssl rand -hex 32)

# ── Write .env file ───────────────────────────────────────────────────────────
cat > "$MAGELLON_DIR/.env" <<EOF
AWS_REGION=$AWS_REGION

MAGELLON_HOME_PATH=/mnt/efs/magellon
MAGELLON_GPFS_PATH=/mnt/efs/gpfs
MAGELLON_JOBS_PATH=/mnt/efs/jobs
MAGELLON_ROOT_DIR=$MAGELLON_DIR

MYSQL_DATABASE=$MYSQL_DATABASE
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MYSQL_PORT=3306

RABBITMQ_DEFAULT_USER=$RABBITMQ_USER
RABBITMQ_DEFAULT_PASS=$RABBITMQ_PASSWORD
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672

DRAGONFLY_PASSWORD=$DRAGONFLY_PASSWORD
DRAGONFLY_PORT=6379

GRAFANA_USER_NAME=$GRAFANA_USER
GRAFANA_USER_PASS=$GRAFANA_PASSWORD

JWT_SECRET_KEY=$JWT_SECRET_KEY

# Frontend uses relative API paths (/web/..., /auth/...) so nginx inside the
# web container can proxy them to the backend container — no CORS, one ALB TG.
API_URL=
MAGELLON_CORS_ALLOWED_ORIGINS=

MAGELLON_FRONTEND_PORT=8080
MAGELLON_BACKEND_PORT=8000
MAGELLON_CTF_PLUGIN_PORT=8035
MAGELLON_FFT_PLUGIN_PORT=8037
MAGELLON_PTOLEMY_PLUGIN_PORT=8038
MAGELLON_TOPAZ_PLUGIN_PORT=8039
MAGELLON_STACK_MAKER_PLUGIN_PORT=8040
MAGELLON_CAN_CLASSIFIER_PLUGIN_PORT=8041
MAGELLON_TEMPLATE_PICKER_PLUGIN_PORT=8042

MAGELLON_RMQ_STEP_EVENTS_FORWARDER=1
MAGELLON_STEP_EVENTS_FORWARDER=1
NATS_URL=nats://nats:4222
EOF
chmod 600 "$MAGELLON_DIR/.env"

# Also place .env where docker compose can find it (relative to repo root)
cp "$MAGELLON_DIR/.env" "$REPO_DIR/Docker/AWS_docker_compose/.env"

# ── Create systemd service ────────────────────────────────────────────────────
cat > /etc/systemd/system/magellon.service <<'UNIT'
[Unit]
Description=Magellon CPU Stack
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/magellon-repo
EnvironmentFile=/opt/magellon/.env
ExecStart=/usr/bin/docker compose \
  -f Docker/AWS_docker_compose/docker-compose.main.yml \
  --env-file /opt/magellon/.env \
  up -d --build
ExecStop=/usr/bin/docker compose \
  -f Docker/AWS_docker_compose/docker-compose.main.yml \
  down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable magellon.service
systemctl start magellon.service

# ── Restore preserved data (accounts, roles, config) from EFS if present ─────
# export_preserve_data.sh (run on the old instance before migration) writes
# a mysqldump to this path. We import it once, then rename it so a reboot
# doesn't re-import stale data.
MIGRATION_FILE="/mnt/efs/magellon/db-migration/preserve_data.sql"
if [ -f "$MIGRATION_FILE" ]; then
  echo "Found preserved migration at $MIGRATION_FILE — waiting for MySQL..."

  TIMEOUT=300; ELAPSED=0
  until docker exec magellon-mysql_container \
      mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
      echo "WARNING: MySQL not ready after $TIMEOUT s — skipping migration import"
      break
    fi
    sleep 5; ELAPSED=$((ELAPSED + 5))
  done

  if docker exec magellon-mysql_container \
      mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; then

    echo "Importing preserved data (accounts, permissions, config)..."
    docker exec -i magellon-mysql_container \
      mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" < "$MIGRATION_FILE"

    # Rename so a reboot doesn't re-import
    mv "$MIGRATION_FILE" "$MIGRATION_FILE.imported-$(date +%Y%m%d%H%M%S)"
    echo "Migration import complete. Import tables (sessions/images) start empty."
  fi
fi

echo "=== Bootstrap complete $(date). Check 'journalctl -u magellon.service' for status. ==="

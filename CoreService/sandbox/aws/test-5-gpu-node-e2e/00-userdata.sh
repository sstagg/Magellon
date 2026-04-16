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

#!/bin/bash
#
# generate-motioncor-gpu-compose.sh — GPU-count-aware MotionCor scaling
#
# Docker Compose has no primitive for "one replica per detected GPU":
# deploy.replicas is a static number, and a GPU device reservation
# isn't distributed across replicas — every replica would see the same
# device_ids and collide on the same physical card. So instead of one
# magellon_motioncor_plugin service in docker-compose.yml, this script
# detects how many GPUs *this* host has at deploy time and generates a
# compose override with one magellon_motioncor_plugin_gpu<N> service
# per GPU, each pinned to a distinct device_id via
# NVIDIA_VISIBLE_DEVICES scoping (the container sees exactly one
# physical GPU, remapped to logical index 0 — matching the plugin's
# hardcoded Gpu='0' task parameter). Re-run this whenever the box's
# GPU count changes (new hardware, GPUs taken offline, etc); it's
# idempotent and always regenerates the full file from scratch.
#
# Usage:
#   ./generate-motioncor-gpu-compose.sh
#   MOTIONCOR_GPU_COUNT=3 ./generate-motioncor-gpu-compose.sh   # force a count
#
# Output: docker-compose.motioncor-gpu.generated.yml (next to this
# script). Not committed to git — see .gitignore. Docker/start.sh
# passes it to `docker compose up` alongside docker-compose.yml; if
# you're invoking compose by hand, do the same:
#   docker compose -f docker-compose.yml -f docker-compose.motioncor-gpu.generated.yml up -d
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_FILE="${SCRIPT_DIR}/docker-compose.motioncor-gpu.generated.yml"

# A GPU count can be forced (e.g. CI, or a box where nvidia-smi is
# present but you want fewer workers than physical GPUs) via
# MOTIONCOR_GPU_COUNT. Otherwise detect it from nvidia-smi.
if [[ -n "${MOTIONCOR_GPU_COUNT:-}" ]]; then
    GPU_COUNT="$MOTIONCOR_GPU_COUNT"
    STRICT_GPU_PINNING=true
    echo "generate-motioncor-gpu-compose: using forced GPU_COUNT=$GPU_COUNT (MOTIONCOR_GPU_COUNT set)"
elif command -v nvidia-smi &>/dev/null && GPU_COUNT="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU')" && [[ "$GPU_COUNT" -gt 0 ]]; then
    STRICT_GPU_PINNING=true
    echo "generate-motioncor-gpu-compose: detected $GPU_COUNT GPU(s) via nvidia-smi"
else
    GPU_COUNT=1
    STRICT_GPU_PINNING=false
    echo "generate-motioncor-gpu-compose: WARNING — nvidia-smi unavailable or reported 0 GPUs." >&2
    echo "generate-motioncor-gpu-compose: generating a single service with an unpinned 'count: all' GPU reservation instead." >&2
fi

{
    echo "# GENERATED FILE — do not edit by hand."
    echo "# Regenerate with: ./generate-motioncor-gpu-compose.sh"
    echo "# Detected/forced GPU_COUNT=${GPU_COUNT} at $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "services:"
} > "$OUT_FILE"

for ((i = 0; i < GPU_COUNT; i++)); do
  STATIC_IP="172.16.238.$((100 + i))"
    cat >> "$OUT_FILE" <<EOF
  magellon_motioncor_plugin_gpu${i}:
    build:
      context: ..
      dockerfile: plugins/magellon_motioncor_plugin/Dockerfile
      args:
        CUDA_IMAGE: \${CUDA_IMAGE}
        MOTIONCOR_BINARY: \${MOTIONCOR_BINARY}
    image: magellon_motioncor_plugin_image
    container_name: magellon_motioncor_plugin_gpu${i}
    user: "\${MAGELLON_UID:-841675}:\${MAGELLON_GID:-841675}"
    restart: unless-stopped
    depends_on:
      - rabbitmq
      - nats
    environment:
      - APP_ENV=production
      - RUN_ENV=docker
      - GPFS_ROOT=\${MAGELLON_GPFS_PATH}
      - JOBS_PATH=\${MAGELLON_JOBS_PATH}
      - CUDA_IMAGE=\${CUDA_IMAGE}
      - MOTIONCOR_BINARY=\${MOTIONCOR_BINARY}
      - DRAGONFLY_HOST=dragonfly
      - DRAGONFLY_PORT=6379
      - DRAGONFLY_PASSWORD=\${DRAGONFLY_PASSWORD:-password}
      - MAGELLON_LOG_DIR=/tmp/magellon-logs
      - MPLCONFIGDIR=/tmp/matplotlib
      - HOME=/tmp
    volumes:
      - \${MAGELLON_HOME_PATH}:/magellon
      - \${MAGELLON_GPFS_PATH}:/gpfs:ro
      - \${MAGELLON_JOBS_PATH}:/jobs
    networks:
      magellon-network:
        ipv4_address: ${STATIC_IP}
    group_add:
      - "\${DOCKER_GID:-498}"
      - "\${MAGELLON_GPFS_GID:-445}"
EOF
    # Only the first replica publishes the plugin's HTTP port — N
    # containers can't all bind the same host port, and nothing
    # outside this plugin depends on a specific replica's port being
    # reachable (discovery/heartbeat ride the message bus, not HTTP).
    if [[ "$i" -eq 0 ]]; then
        cat >> "$OUT_FILE" <<EOF
    ports:
      - "127.0.0.1:\${MAGELLON_MOTIONCOR_PLUGIN_PORT}:80"
EOF
    fi

    if [[ "$STRICT_GPU_PINNING" == "true" ]]; then
        cat >> "$OUT_FILE" <<EOF
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${i}"]
              capabilities: [gpu]
EOF
    else
        cat >> "$OUT_FILE" <<EOF
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
EOF
    fi
    echo "" >> "$OUT_FILE"
done

echo "generate-motioncor-gpu-compose: wrote $GPU_COUNT service(s) to $OUT_FILE"

#!/bin/bash
#
# generate-ctf-compose.sh — parallel CTF consumers
#
# CTF (ctffind) is CPU-bound, not GPU-bound, so unlike MotionCor its
# replica count isn't detected from hardware — it's a fixed number you
# choose based on available CPU cores. But it hits the exact same
# Docker Compose limitation MotionCor did: a service with a hardcoded
# container_name, a fixed host port, and a fixed static IP can't be
# scaled to more than one replica (Compose refuses the name/port/IP
# collision). So instead of one magellon_ctf_plugin service in
# docker-compose.yml, this generates one magellon_ctf_plugin_N service
# per replica, all wired as competing consumers on the same
# ctf_tasks_queue/ctf_out_tasks_queue.
#
# Usage:
#   ./generate-ctf-compose.sh
#   CTF_REPLICA_COUNT=8 ./generate-ctf-compose.sh   # override the count
#
# Output: docker-compose.ctf-scale.generated.yml (next to this script).
# Not committed to git — see .gitignore. Docker/start.sh and
# setup-magellon.sh pass it to `docker compose up` alongside
# docker-compose.yml; if invoking compose by hand, do the same:
#   docker compose -f docker-compose.yml -f docker-compose.ctf-scale.generated.yml up -d
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_FILE="${SCRIPT_DIR}/docker-compose.ctf-scale.generated.yml"
REPLICA_COUNT="${CTF_REPLICA_COUNT:-4}"

echo "generate-ctf-compose: generating $REPLICA_COUNT CTF replica(s)"

{
    echo "# GENERATED FILE — do not edit by hand."
    echo "# Regenerate with: ./generate-ctf-compose.sh"
    echo "# REPLICA_COUNT=${REPLICA_COUNT} at $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "services:"
} > "$OUT_FILE"

for ((i = 0; i < REPLICA_COUNT; i++)); do
    cat >> "$OUT_FILE" <<EOF
  magellon_ctf_plugin_${i}:
    build:
      context: ..
      dockerfile: plugins/magellon_ctf_plugin/Dockerfile
    image: magellon_ctf_plugin_image
    container_name: magellon_ctf_plugin_${i}
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
      - magellon-network
    group_add:
      - "\${DOCKER_GID:-498}"
      - "\${MAGELLON_GPFS_GID:-445}"
EOF
    # Only replica 0 publishes the plugin's HTTP port — N containers
    # can't all bind the same host port, and a CoreService contract
    # test (CoreService/tests/contracts) expects exactly one reachable
    # instance, not a specific replica beyond "one exists".
    if [[ "$i" -eq 0 ]]; then
        cat >> "$OUT_FILE" <<EOF
    ports:
      - "127.0.0.1:\${MAGELLON_CTF_PLUGIN_PORT}:8000"
EOF
    fi
    echo "" >> "$OUT_FILE"
done

echo "generate-ctf-compose: wrote $REPLICA_COUNT service(s) to $OUT_FILE"

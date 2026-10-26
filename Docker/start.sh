#!/bin/bash
VOLUMES=(
  "mysql_data"
  "mysql_conf"
  "mysql_init"
  "rabbitmq_data"
  "prometheus_config"
  "grafana_storage"
  "grafana_temp"
  "magellon_home"
  "magellon_jobs"
  "postgres_data"
  "postgres_conf"
  "rabbitmq-data"
  "app_data"
)

# Step 1: Create Docker volumes
echo "Creating required Docker volumes..."
for volume in "${VOLUMES[@]}"; do
  if ! docker volume inspect "$volume" &>/dev/null; then
    docker volume create "$volume"
    echo "Created volume: $volume"
  else
    echo "Volume already exists: $volume"
  fi
done

# Step 2: Generate the GPU-count-aware MotionCor compose overlay.
# One magellon_motioncor_plugin service can't scale itself to however
# many GPUs this box has, so it's generated per-deployment instead of
# hardcoded in docker-compose.yml — see generate-motioncor-gpu-compose.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/generate-motioncor-gpu-compose.sh"

# CTF (CPU-bound, fixed replica count) hits the same Compose scaling
# limitation MotionCor did — see generate-ctf-compose.sh.
"$SCRIPT_DIR/generate-ctf-compose.sh"

# Step 3: Start Docker Compose
if command -v docker-compose &> /dev/null; then
    DOCKER_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_CMD="docker compose"
else
    echo "Neither 'docker-compose' nor 'docker compose' is available in the PATH."
    exit 1
fi

echo "Using command: $DOCKER_CMD"

$DOCKER_CMD -f "$SCRIPT_DIR/docker-compose.yml" -f "$SCRIPT_DIR/docker-compose.motioncor-gpu.generated.yml" -f "$SCRIPT_DIR/docker-compose.ctf-scale.generated.yml" --profile default up -d

# Step 4: Wait for services to be ready (optional)
# You can add a sleep here to give the services some time to start, or use a more sophisticated health check
sleep 15


#open_urls() {
#  local urls=(
#    "http://localhost:8080/en/panel/images"
#    "http://localhost:8000"
#    "http://localhost:15672"
#    "http://localhost:8500"
#    "http://localhost:3000"
#    "http://localhost:9090"
#  )




# Step 5: Open browser with links
# Replace the URL with the desired URL for your service
if which xdg-open > /dev/null
then
  xdg-open "http://localhost:8080/en/panel/images"
  xdg-open "http://localhost:8000"

elif which gnome-open > /dev/null
then
  gnome-open "http://localhost:8080/en/panel/images"
  gnome-open "http://localhost:8000"

elif which open > /dev/null    # For macOS
then
  open "http://localhost:8080/en/panel/images"
  open "http://localhost:8000"

fi

#!/bin/bash

# Magellon setup script - Fixed CUDA parsing
# This script creates the directory structure for Magellon,
# copies services data, updates .env file, and starts Docker containers

set -e  # Exit immediately if a command exits with non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        *)          echo "unknown";;
    esac
}

# Cross-platform sed in-place edit
sed_inplace() {
    local sed_cmd="$1"
    local file="$2"

    if [[ "$(detect_os)" == "macos" ]]; then
        sed -i '' "$sed_cmd" "$file"
    else
        sed -i "$sed_cmd" "$file"
    fi
}

check_gpu() {
    # Run the nvidia-smi command inside the Docker container to check for GPU availability
    echo "Checking GPU availability using nvidia-smi..."

    # Ensure Docker is running the CUDA container correctly with nvidia-smi
    output=$(docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi 2>&1) || true

    # Debug output: Show the raw output from the command
    echo "nvidia-smi command output:"
    echo "$output"

    # Check if NVIDIA GPU information is in the output
    if echo "$output" | grep -q "NVIDIA-SMI"; then
        echo "GPU detected and accessible."
    else
        echo "⚠️ WARNING: Docker cannot detect GPU or there was an issue with the nvidia-smi command."
        echo "Proceeding without GPU support..."
        echo "Output from nvidia-smi command:"
        echo "$output"
    fi
}

get_cuda_image() {
    local version="$1"
    IFS='.' read -r -a parts <<< "$version"

    # Ensure at least two parts (major.minor)
    while [ ${#parts[@]} -lt 2 ]; do
        parts+=("0")
    done

    local major="${parts[0]}"
    local minor="${parts[1]}"
    local version_key=""

    # Determine the version key
    if [ "$major" -eq 11 ] && [ "$minor" -lt 9 ]; then
        version_key="11.$minor"
    elif [ "$major" -eq 11 ] && [ "$minor" -ge 9 ]; then
        version_key="11.8"
    elif [ "$major" -eq 12 ] && [ "$minor" -lt 1 ]; then
        version_key="11.8"
    elif [ "$major" -ge 12 ] && [ "$minor" -ge 1 ]; then
        version_key="12.1"
    else
        echo "ERROR: Invalid version"
        echo "Suggestion: The Minimum value for version is 11.1"
        echo "Run CMD: 'nvidia-smi' on your machine and provide the cuda version shown"
        exit 1
    fi

    # Return values directly without echo to avoid parsing issues
    case "$version_key" in
        "11.1")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.1.1-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda111_Mar312023"
            ;;
        "11.2")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.2.2-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda112_Mar312023"
            ;;
        "11.3")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.3.1-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda113_Mar312023"
            ;;
        "11.4")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.4.3-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda114_Mar312023"
            ;;
        "11.5")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.5.2-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda115_Mar312023"
            ;;
        "11.6")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.6.1-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda116_Mar312023"
            ;;
        "11.7")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.7.1-devel-ubuntu20.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda117_Mar312023"
            ;;
        "11.8")
            CUDA_IMAGE_RESULT="nvidia/cuda:11.8.0-devel-ubuntu22.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda118_Mar312023"
            ;;
        "12.1")
            CUDA_IMAGE_RESULT="nvidia/cuda:12.1.0-devel-ubuntu22.04"
            MOTIONCOR_BINARY_RESULT="MotionCor2_1.6.4_Cuda121_Mar312023"
            ;;
        *)
            echo "ERROR: Unsupported version key: $version_key"
            exit 1
            ;;
    esac
}

# Check if root directory is provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <root_directory> <cuda_version>"
    echo "  Example: $0 /home/user/magellon 11.8"
    exit 1
fi

ROOT_DIR=$1
CUDA_VERSION=$2

if [[ "$(id -u)" -eq 0 ]]; then
    echo "ERROR: Run this script as the deployment user, not as root."
    exit 1
fi

if [[ -z "$ROOT_DIR" || "$ROOT_DIR" == "/" ]]; then
    echo "ERROR: ROOT_DIR must be a non-root directory."
    exit 1
fi

umask 0002
MAGELLON_UID_VALUE="$(id -u)"
MAGELLON_GID_VALUE="$(id -g)"
DOCKER_GID_VALUE="$(getent group docker | cut -d: -f3)"
MAGELLON_GPFS_GID_VALUE="$(getent group cryo_stagg | cut -d: -f3)"

if [[ -z "$DOCKER_GID_VALUE" || -z "$MAGELLON_GPFS_GID_VALUE" ]]; then
    echo "ERROR: Could not resolve docker and cryo_stagg group IDs."
    exit 1
fi

if [[ ! -f .env || ! -r .env ]]; then
    echo "ERROR: .env must exist and be readable from the Docker directory."
    exit 1
fi

MAGELLON_GPFS_PATH_VALUE="$(sed -n 's/^MAGELLON_GPFS_PATH=//p' .env | head -n 1)"
if [[ -z "$MAGELLON_GPFS_PATH_VALUE" || ! -d "$MAGELLON_GPFS_PATH_VALUE" ]]; then
    echo "ERROR: MAGELLON_GPFS_PATH in .env must point to the mounted Leginon source tree."
    exit 1
fi

# Call the function and get results through global variables
get_cuda_image "$CUDA_VERSION"
cuda_image="$CUDA_IMAGE_RESULT"
motiocor_binary="$MOTIONCOR_BINARY_RESULT"

echo "CUDA Image: $cuda_image"
echo "MotionCor Binary: $motiocor_binary"
echo "=== Magellon Setup ==="
echo "Setting up Magellon in: $ROOT_DIR"
echo "Detected OS: $(detect_os)"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check command existence
check_command() {
    if ! command -v $1 &> /dev/null; then
        log "ERROR: '$1' command not found. Please install it first."
        if [[ "$(detect_os)" == "macos" ]]; then
            echo "  Suggestion: brew install $1"
        else
            echo "  Suggestion: sudo apt-get update && sudo apt-get install -y $1"
        fi
        exit 1
    fi
}

# Check for Docker
log "Checking prerequisites..."
check_command docker

# Determine which Docker Compose command to use
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    log "Using docker-compose command"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    log "Using docker compose command"
else
    log "ERROR: Neither docker-compose nor docker compose plugin found."
    log "Please install either Docker Compose v1 (docker-compose) or Docker Compose v2 (docker compose plugin)"
    exit 1
fi

check_gpu

# Create main directories
log "Creating directory structure..."
# Define directory structure as an array
# Only create non-services directories since services will be copied entirely
directories=(
    "$ROOT_DIR/home"
    "$ROOT_DIR/jobs"
)

# Create directories
for dir in "${directories[@]}"; do
    mkdir -p "$dir"
done

# Copy service configuration, but never copy a live MySQL data directory into
# a new deployment.
if [ -d "$REPO_ROOT/services" ]; then
    log "Copying services directory and its contents..."

    mkdir -p "$ROOT_DIR/services"
    tar -C "$REPO_ROOT" --exclude='services/mysql/data' -cf - services \
        | tar -C "$ROOT_DIR" -xf -

    if [ $? -ne 0 ]; then
        log "WARNING: Failed to copy all services. Check permissions and try again."
    else
        log "Services directory copied successfully"
    fi
else
    log "WARNING: 'services' directory not found in current location"
    log "Make sure to manually copy any required data files"
fi
mkdir -p "$ROOT_DIR/services/mysql/data"
mkdir -p "$ROOT_DIR/services/mysql/conf"
mkdir -p "$ROOT_DIR/services/mysql/init"
mkdir -p "$ROOT_DIR/services/prometheus"
# Group write is shared with the allocation group. Other users get search-only
# access so the root-squashed Docker daemon can traverse NFS bind-mount paths.
# File contents remain governed by their own modes; the GPFS source is untouched.
log "Setting group-shared permissions for application and Docker bind mounts..."

writable_dirs=(
    "$ROOT_DIR"
    "$ROOT_DIR/home"
    "$ROOT_DIR/jobs"
    "$ROOT_DIR/services/mysql/data"
    "$ROOT_DIR/services/mysql/conf"
    "$ROOT_DIR/services/mysql/init"
    "$ROOT_DIR/services/prometheus"
)

# 2771 keeps writes with owner/group while allowing NFS root-squashed traversal.
for dir in "${writable_dirs[@]}"; do
    if [ -d "$dir" ]; then
        if ! chmod 2771 "$dir" 2>/dev/null; then
            log "ERROR: Cannot set permissions on $dir as $(id -un)"
            exit 1
        fi
    fi
done

log "Writable directories created with owner/group permissions; GPFS source was left unchanged."

# Check if we're in the right directory (where docker-compose.yml is)
if [ ! -f "docker-compose.yml" ]; then
    log "ERROR: docker-compose.yml not found in current directory."
    log "Please run this script from the directory containing docker-compose.yml"
    exit 1
fi

# Make sure the .env file exists and update it
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found."
    log "Please make sure .env file exists in the current directory"
    exit 1
else
    env_updates=(
        "MAGELLON_HOME_PATH=${ROOT_DIR}/home"
        "MAGELLON_GPFS_PATH=${MAGELLON_GPFS_PATH_VALUE}"
        "MAGELLON_JOBS_PATH=${ROOT_DIR}/jobs"
        "MAGELLON_ROOT_DIR=${ROOT_DIR}"
        "MAGELLON_UID=${MAGELLON_UID_VALUE}"
        "MAGELLON_GID=${MAGELLON_GID_VALUE}"
        "MAGELLON_GPFS_GID=${MAGELLON_GPFS_GID_VALUE}"
        "DOCKER_GID=${DOCKER_GID_VALUE}"
        "CUDA_IMAGE=${cuda_image}"
        "MOTIONCOR_BINARY=${motiocor_binary}"
    )
    needs_env_update=false
    for entry in "${env_updates[@]}"; do
        if ! grep -Fqx "$entry" .env; then
            needs_env_update=true
            break
        fi
    done

    if [[ "$needs_env_update" == "true" ]]; then
        if [[ ! -w .env ]]; then
            log "ERROR: .env needs updates but is not writable by $(id -un)."
            log "Grant cryo_magellon write access to this deployment copy or use an account-owned checkout."
            exit 1
        fi

        cp .env .env.backup
        chmod 600 .env .env.backup
        for entry in "${env_updates[@]}"; do
            key="${entry%%=*}"
            value="${entry#*=}"
            if grep -q "^${key}=" .env; then
                sed_inplace "s|^${key}=.*|${key}=${value}|" .env
            else
                printf '%s=%s\n' "$key" "$value" >> .env
            fi
        done
        log ".env updated; a backup was saved as .env.backup"
    else
        log ".env already has the requested paths and runtime IDs; left unchanged."
    fi
fi

# Generate the GPU-count-aware MotionCor compose overlay. One
# magellon_motioncor_plugin service can't scale itself to however many
# GPUs this box has — deploy.replicas is a static number and a GPU
# device reservation isn't distributed across replicas — so instead of
# a single hardcoded service in docker-compose.yml, this generates one
# GPU-pinned service per detected GPU. Safe to re-run: it always
# regenerates the file from scratch. See generate-motioncor-gpu-compose.sh.
log "Generating GPU-count-aware MotionCor compose overlay..."
"$SCRIPT_DIR/generate-motioncor-gpu-compose.sh"

# CTF (CPU-bound, fixed replica count — default 4, override via
# CTF_REPLICA_COUNT) hits the same Compose scaling limitation MotionCor
# did: a hardcoded container_name/port/IP blocks scaling to >1 replica.
# See generate-ctf-compose.sh.
log "Generating CTF compose overlay..."
"$SCRIPT_DIR/generate-ctf-compose.sh"

COMPOSE_FILES=(-f docker-compose.yml -f "$SCRIPT_DIR/docker-compose.motioncor-gpu.generated.yml" -f "$SCRIPT_DIR/docker-compose.ctf-scale.generated.yml")

# Start the Caddy HTTPS proxy only on hosts that have a public domain
# configured in .env (e.g. the RCC deployment); local installs skip it.
MAGELLON_DOMAIN_VALUE=$(grep -E '^MAGELLON_DOMAIN=' .env | cut -d= -f2- || true)
if [ -n "$MAGELLON_DOMAIN_VALUE" ]; then
    COMPOSE_FILES+=(--profile proxy)
    log "Public domain configured ($MAGELLON_DOMAIN_VALUE) - Caddy HTTPS proxy will be started"
fi

# Start Docker Compose with proper error handling
log "Starting Docker containers..."
# (No --scale flags: the single magellon_ctf_plugin / magellon_motioncor_plugin
# services were replaced by the generated per-replica / per-GPU services, and
# scaling a service that doesn't exist makes compose refuse to start at all.)
if $DOCKER_COMPOSE_CMD "${COMPOSE_FILES[@]}" up -d --build; then
    log "Docker containers started successfully"
else
    log "ERROR: Failed to start Docker containers. Check logs with '$DOCKER_COMPOSE_CMD ${COMPOSE_FILES[*]} logs'"
    exit 1
fi

# debug_queue receives copies of bus messages but has no consumer, so it
# grows without bound. Keep one day of messages (and at most 50,000, oldest
# dropped first). Policies live in RabbitMQ's data volume; setting it again
# is harmless, and a fresh install gets it here.
log "Applying RabbitMQ retention policy to debug_queue (1 day)..."
for _ in $(seq 1 30); do
    if docker exec magellon-rabbitmq-container rabbitmqctl set_policy debug-queue-retention '^debug_queue$' \
        '{"message-ttl":86400000,"max-length":50000,"overflow":"drop-head"}' \
        --apply-to queues --priority 1 >/dev/null 2>&1; then
        log "debug_queue retention policy set"
        break
    fi
    sleep 2
done || true

log "Setup complete! Magellon services should now be running."
log "You can check container status with '$DOCKER_COMPOSE_CMD ${COMPOSE_FILES[*]} ps'"

# Wait for services to start (but don't try to open browser in headless environments)
log "Waiting for services to start up (15 seconds)..."
sleep 15

log "Magellon is now available at:"
log "  - http://localhost:8080/en/panel/images"
log "  - http://localhost:8000"
if [ -n "$MAGELLON_DOMAIN_VALUE" ]; then
    log "  - https://$MAGELLON_DOMAIN_VALUE"
fi

# Cross-platform browser opening
open_browser() {
    local url="$1"

    if [[ "$(detect_os)" == "macos" ]]; then
        open "$url" 2>/dev/null || log "Could not open browser automatically"
    elif [[ "$(detect_os)" == "linux" ]]; then
        if [ -n "$DISPLAY" ]; then
            # Try different Linux browser openers
            if command -v xdg-open &> /dev/null; then
                xdg-open "$url" 2>/dev/null || true
            elif command -v gnome-open &> /dev/null; then
                gnome-open "$url" 2>/dev/null || true
            fi
        else
            log "Running in non-graphical environment. Please access URLs from a browser manually."
        fi
    fi
}

# Try to open browser
if [[ "$(detect_os)" == "macos" ]] || [ -n "$DISPLAY" ]; then
    log "Attempting to open browser links..."
    open_browser "http://localhost:8080/en/panel/images"
    open_browser "http://localhost:8000"
fi

log "=== Setup process completed! ==="
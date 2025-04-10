#!/bin/bash

# Magellon setup script
# This script creates the directory structure for Magellon,
# copies services data, updates .env file, and starts Docker containers

set -e  # Exit immediately if a command exits with non-zero status

get_cuda_image() {
    local version="$1"
    IFS='.' read -r -a parts <<< "$version"

    # Ensure at least three parts (major.minor.patch)
    while [ ${#parts[@]} -lt 2 ]; do
        parts+=("0")
    done

    local major="${parts[0]}"
    local minor="${parts[1]}"

    # Define mappings in associative arrays (dictionaries)
    declare -A cuda_images=(
        ["11.1"]="nvidia/cuda:11.1.1-devel-ubuntu20.04"
        ["11.2"]="nvidia/cuda:11.2.2-devel-ubuntu20.04"
        ["11.3"]="nvidia/cuda:11.3.1-devel-ubuntu20.04"
        ["11.4"]="nvidia/cuda:11.4.3-devel-ubuntu20.04"
        ["11.5"]="nvidia/cuda:11.5.2-devel-ubuntu20.04"
        ["11.6"]="nvidia/cuda:11.6.1-devel-ubuntu20.04"
        ["11.7"]="nvidia/cuda:11.7.1-devel-ubuntu20.04"
        ["11.8"]="nvidia/cuda:11.8.0-devel-ubuntu22.04"
        ["12.1"]="nvidia/cuda:12.1.0-devel-ubuntu22.04"
    )

    declare -A motioncor_binaries=(
        ["11.1"]="MotionCor2_1.6.4_Cuda111_Mar312023"
        ["11.2"]="MotionCor2_1.6.4_Cuda112_Mar312023"
        ["11.3"]="MotionCor2_1.6.4_Cuda113_Mar312023"
        ["11.4"]="MotionCor2_1.6.4_Cuda114_Mar312023"
        ["11.5"]="MotionCor2_1.6.4_Cuda115_Mar312023"
        ["11.6"]="MotionCor2_1.6.4_Cuda116_Mar312023"
        ["11.7"]="MotionCor2_1.6.4_Cuda117_Mar312023"
        ["11.8"]="MotionCor2_1.6.4_Cuda118_Mar312023"
        ["12.1"]="MotionCor2_1.6.4_Cuda121_Mar312023"
    )

    local cuda_image=""
    local motioncor_binary=""
    local version_key=""

    # Determine the version key to use for lookup
    if (( major == 11 && minor < 9 )); then
        version_key="11.$minor"
    elif ((major==11 && minor>=9)); then
        version_key="11.8"
    elif ((major==12 && minor<1)); then
        version_key="11.8"
    elif (( major >= 12 && minor>=1)); then
        version_key="12.1"
    else
        cuda_image="Invalid version"
        motioncor_binary="Invalid"
        echo "$cuda_image $motioncor_binary"
        return
    fi
    echo "${version_key}"
    # Look up values in the dictionaries
    cuda_image="${cuda_images[$version_key]}"
    motioncor_binary="${motioncor_binaries[$version_key]}"

    # Return values as space-separated output
    echo "$cuda_image $motioncor_binary"
}

# Check if root directory is provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <root_directory> <cuda_version>"
    echo "  Example: $0 /home/user/magellon 11.8"
    exit 1
fi

ROOT_DIR=$1
CUDA_VERSION=$2
cuda_output=$(get_cuda_image "$CUDA_VERSION")
cuda_image=$(echo "$cuda_output" | awk '{print $1}')
motiocor_binary=$(echo "$cuda_output" | awk '{print $2}')

echo "CUDA Image: $cuda_image"
echo "MotionCor Binary: $motiocor_binary"
echo "=== Magellon Setup ==="
echo "Setting up Magellon in: $ROOT_DIR"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check command existence
check_command() {
    if ! command -v $1 &> /dev/null; then
        log "ERROR: '$1' command not found. Please install it first."
        echo "  Suggestion: sudo apt-get update && sudo apt-get install -y $1"
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

# Create main directories
log "Creating directory structure..."
# Define directory structure as an array
directories=(
    "$ROOT_DIR/services/mysql/data"
    "$ROOT_DIR/services/mysql/conf"
    "$ROOT_DIR/services/mysql/init"
    "$ROOT_DIR/services/consul/data"
    "$ROOT_DIR/services/consul/config"
    "$ROOT_DIR/services/prometheus"
    "$ROOT_DIR/gpfs"
    "$ROOT_DIR/home"
    "$ROOT_DIR/jobs"
)

# Create directories
for dir in "${directories[@]}"; do
    mkdir -p "$dir"
done

# Copy services directory if it exists in current directory
if [ -d "services" ]; then
    log "Copying services directory and its contents..."
    cp -r services/* "$ROOT_DIR/services/"
    if [ $? -ne 0 ]; then
        log "WARNING: Failed to copy all services. Check permissions and try again."
    else
        log "Services directory copied successfully"
    fi
else
    log "WARNING: 'services' directory not found in current location"
    log "Make sure to manually copy any required data files"
fi

# Set permissions with better security practices
log "Setting directory permissions..."

# Define directories that need 777 permissions
writable_dirs=(
    "$ROOT_DIR/gpfs"
    "$ROOT_DIR/home"
    "$ROOT_DIR/jobs"
    "$ROOT_DIR/services/mysql/data"
    "$ROOT_DIR/services/mysql/conf"
    "$ROOT_DIR/services/mysql/init"
    "$ROOT_DIR/services/consul/data"
    "$ROOT_DIR/services/consul/config"
    "$ROOT_DIR/services/prometheus"
)

# Set 777 permissions on writable directories
for dir in "${writable_dirs[@]}"; do
    chmod -R 777 "$dir" 2>/dev/null || log "WARNING: Failed to set permissions on $dir"
done

log "Directory structure created with appropriate permissions"

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
    # Update .env file with the new paths
    log "Updating .env file with correct paths..."
    # Create a backup of the original .env file
    cp .env .env.backup

    # Update paths in .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SED_CMD="sed -i ''"
    else
        SED_CMD="sed -i"
    fi

    # Define environment variable mappings
    declare -A env_vars=(
        ["MAGELLON_HOME_PATH"]="$ROOT_DIR/home"
        ["MAGELLON_GPFS_PATH"]="$ROOT_DIR/gpfs"
        ["MAGELLON_JOBS_PATH"]="$ROOT_DIR/jobs"
        ["MAGELLON_ROOT_DIR"]="$ROOT_DIR"
        ["CUDA_IMAGE"]="$cuda_image"
        ["MOTIONCOR_BINARY"]="$motiocor_binary"
    )

    # Update each environment variable
    for var_name in "${!env_vars[@]}"; do
        value="${env_vars[$var_name]}"
        $SED_CMD "s|$var_name=.*|$var_name=$value|g" .env
    done

    log ".env file updated successfully (backup created as .env.backup)"
fi

# Start Docker Compose with proper error handling
log "Starting Docker containers..."
if $DOCKER_COMPOSE_CMD up -d; then
    log "Docker containers started successfully"
else
    log "ERROR: Failed to start Docker containers. Check logs with '$DOCKER_COMPOSE_CMD logs'"
    exit 1
fi

log "Setup complete! Magellon services should now be running."
log "You can check container status with '$DOCKER_COMPOSE_CMD ps'"

# Wait for services to start (but don't try to open browser in headless environments)
log "Waiting for services to start up (15 seconds)..."
sleep 15

log "Magellon is now available at:"
log "  - http://localhost:8080/en/panel/images"
log "  - http://localhost:8000"

# Dictionary for browser openers
declare -A browser_openers=(
    ["xdg-open"]="xdg-open"
    ["gnome-open"]="gnome-open"
    ["open"]="open"  # For macOS
)

# Check if this is an interactive environment with a desktop
if [ -n "$DISPLAY" ]; then
    log "Attempting to open browser links..."
    browser_found=false

    # Try each browser opener
    for cmd in "${!browser_openers[@]}"; do
        if which "$cmd" > /dev/null; then
            browser_found=true
            "$cmd" "http://localhost:8080/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
            "$cmd" "http://localhost:8000" 2>/dev/null || log "Could not open browser automatically"
            break
        fi
    done

    if [ "$browser_found" = false ]; then
        log "No compatible browser opener found. Please open the URLs manually."
    fi
else
    log "Running in non-graphical environment. Please access URLs from a browser manually."
fi

log "=== Setup process completed! ==="
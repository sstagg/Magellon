#!/bin/bash

# Magellon setup script
# This script creates the directory structure for Magellon,
# copies services data, updates .env file, and starts Docker containers

set -e  # Exit immediately if a command exits with non-zero status

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
        echo "Invalid version"
        echo "Suggestion: The Minimum value for version is 11.1"
        echo "Run CMD: 'nvidia-smi' on your machine and provide the cuda version shown"
        return
    fi

    echo "$version_key"

    # Set values using case statements
    local cuda_image=""
    local motioncor_binary=""

    case "$version_key" in
        "11.1")
            cuda_image="nvidia/cuda:11.1.1-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda111_Mar312023"
            ;;
        "11.2")
            cuda_image="nvidia/cuda:11.2.2-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda112_Mar312023"
            ;;
        "11.3")
            cuda_image="nvidia/cuda:11.3.1-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda113_Mar312023"
            ;;
        "11.4")
            cuda_image="nvidia/cuda:11.4.3-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda114_Mar312023"
            ;;
        "11.5")
            cuda_image="nvidia/cuda:11.5.2-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda115_Mar312023"
            ;;
        "11.6")
            cuda_image="nvidia/cuda:11.6.1-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda116_Mar312023"
            ;;
        "11.7")
            cuda_image="nvidia/cuda:11.7.1-devel-ubuntu20.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda117_Mar312023"
            ;;
        "11.8")
            cuda_image="nvidia/cuda:11.8.0-devel-ubuntu22.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda118_Mar312023"
            ;;
        "12.1")
            cuda_image="nvidia/cuda:12.1.0-devel-ubuntu22.04"
            motioncor_binary="MotionCor2_1.6.4_Cuda121_Mar312023"
            ;;
        *)
            echo "Unsupported version key: $version_key"
            return
            ;;
    esac

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

check_gpu

# Create main directories
log "Creating directory structure..."
# Define directory structure as an array
# Only create non-services directories since services will be copied entirely
directories=(
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

    # Copy entire services directory structure
    cp -r services "$ROOT_DIR/"

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
)

# Set 777 permissions on main directories
for dir in "${writable_dirs[@]}"; do
    if [ -d "$dir" ]; then
        chmod -R 777 "$dir" 2>/dev/null || log "WARNING: Failed to set permissions on $dir"
    fi
done

# Set permissions for services directories if they exist
if [ -d "$ROOT_DIR/services" ]; then
    # Set 777 for data directories that need write access
    service_data_dirs=(
        "$ROOT_DIR/services/mysql/data"
        "$ROOT_DIR/services/consul/data"
    )

    for dir in "${service_data_dirs[@]}"; do
        if [ -d "$dir" ]; then
            chmod -R 777 "$dir" 2>/dev/null || log "WARNING: Failed to set permissions on $dir"
        fi
    done

    # Set appropriate permissions for config files
    chmod -R 755 "$ROOT_DIR/services" 2>/dev/null || log "WARNING: Failed to set base permissions on services"
fi

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

    # Define environment variable mappings
    declare -A env_updates=(
        ["MAGELLON_HOME_PATH"]="$ROOT_DIR/home"
        ["MAGELLON_GPFS_PATH"]="$ROOT_DIR/gpfs"
        ["MAGELLON_JOBS_PATH"]="$ROOT_DIR/jobs"
        ["MAGELLON_ROOT_DIR"]="$ROOT_DIR"
        ["CUDA_IMAGE"]="$cuda_image"
        ["MOTIONCOR_BINARY"]="$motiocor_binary"
    )

    # Create a temporary file
    temp_file=$(mktemp)

    # Process each line of the .env file
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        if [[ -z "$line" ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
            echo "$line" >> "$temp_file"
            continue
        fi

        # Extract variable name (everything before the first =)
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            var_name=$(echo "$var_name" | xargs)  # Trim whitespace

            # Check if this variable needs to be updated
            if [[ -n "${env_updates[$var_name]}" ]]; then
                echo "${var_name}=${env_updates[$var_name]}" >> "$temp_file"
                log "Updated: ${var_name}=${env_updates[$var_name]}"
            else
                echo "$line" >> "$temp_file"
            fi
        else
            echo "$line" >> "$temp_file"
        fi
    done < .env

    # Replace the original .env file with the updated one
    mv "$temp_file" .env

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
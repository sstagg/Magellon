#!/bin/bash

# Magellon setup script
# This script creates the directory structure for Magellon,
# copies services data, updates .env file, and starts Docker containers

set -e  # Exit immediately if a command exits with non-zero status


# Check if root directory is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <root_directory>"
    echo "  Example: $0 /home/user/magellon"
    exit 1
fi
ROOT_DIR=$1
# ROOT_DIR=$1
echo "=== Magellon Setup ==="
echo "Setting up Magellon in: $ROOT_DIR"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

#Function to check command existence
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
mkdir -p "$ROOT_DIR/services/mysql/data"
mkdir -p "$ROOT_DIR/services/mysql/conf"
mkdir -p "$ROOT_DIR/services/mysql/init"
mkdir -p "$ROOT_DIR/services/consul/data"
mkdir -p "$ROOT_DIR/services/consul/config"
mkdir -p "$ROOT_DIR/services/prometheus"
mkdir -p "$ROOT_DIR/gpfs"
mkdir -p "$ROOT_DIR/home"
mkdir -p "$ROOT_DIR/jobs"

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
# Only set 755 on directories that need execution, 644 on files
# find "$ROOT_DIR/services" -type d -exec chmod 755 {} \; 2>/dev/null || log "WARNING: Some permission changes failed"
# find "$ROOT_DIR/services" -type f -exec chmod 644 {} \; 2>/dev/null || log "WARNING: Some permission changes failed"
# Set 777 only where absolutely necessary (for shared directories)
chmod -R 777 "$ROOT_DIR/gpfs" 2>/dev/null || log "WARNING: Failed to set permissions on gpfs directory"
chmod -R 777 "$ROOT_DIR/home" 2>/dev/null || log "WARNING: Failed to set permissions on home directory"
chmod -R 777 "$ROOT_DIR/jobs" 2>/dev/null || log "WARNING: Failed to set permissions on jobs directory"
chmod -R 777 "$ROOT_DIR/services/mysql/data"
chmod -R 777 "$ROOT_DIR/services/mysql/conf"
chmod -R 777 "$ROOT_DIR/services/mysql/init"
chmod -R 777 "$ROOT_DIR/services/consul/data"
chmod -R 777 "$ROOT_DIR/services/consul/config"
chmod -R 777 "$ROOT_DIR/services/prometheus"
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

    # Use the correct sed command
    $SED_CMD "s|MAGELLON_HOME_PATH=.*|MAGELLON_HOME_PATH=$ROOT_DIR/home|g" .env
    $SED_CMD "s|MAGELLON_GPFS_PATH=.*|MAGELLON_GPFS_PATH=$ROOT_DIR/gpfs|g" .env
    $SED_CMD "s|MAGELLON_JOBS_PATH=.*|MAGELLON_JOBS_PATH=$ROOT_DIR/jobs|g" .env
    $SED_CMD "s|MAGELLON_ROOT_DIR=.*|MAGELLON_ROOT_DIR=$ROOT_DIR|g" .env

    log ".env file updated successfully (backup created as .env.backup)"
fi

Start Docker Compose with proper error handling
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

# Check if this is an interactive environment with a desktop
if [ -n "$DISPLAY" ]; then
    log "Attempting to open browser links..."
    if which xdg-open > /dev/null; then
        xdg-open "http://localhost:8080/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        xdg-open "http://localhost:8000" 2>/dev/null || log "Could not open browser automatically"
    elif which gnome-open > /dev/null; then
        gnome-open "http://localhost:8080/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        gnome-open "http://localhost:8000" 2>/dev/null || log "Could not open browser automatically"
    elif which open > /dev/null; then    # For macOS
        open "http://localhost:8080/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        open "http://localhost:8000" 2>/dev/null || log "Could not open browser automatically"
    else
        log "No compatible browser opener found. Please open the URLs manually."
    fi
else
    log "Running in non-graphical environment. Please access URLs from a browser manually."
fi

log "=== Setup process completed! ==="
#!/bin/bash

# This script creates the directory structure for Magellon,
# copies services data, updates .env file, starts Docker containers,
# and opens browser links

# Check if root directory is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <root_directory>"
    exit 1
fi

ROOT_DIR=$1
echo "Creating directory structure in $ROOT_DIR"

# Create main directories
mkdir -p "$ROOT_DIR/opt/magellon/services/mysql/data"
mkdir -p "$ROOT_DIR/opt/magellon/services/mysql/conf"
mkdir -p "$ROOT_DIR/opt/magellon/services/mysql/init"
mkdir -p "$ROOT_DIR/opt/magellon/services/consul/data"
mkdir -p "$ROOT_DIR/opt/magellon/services/consul/config"
mkdir -p "$ROOT_DIR/opt/magellon/services/prometheus"
mkdir -p "$ROOT_DIR/gpfs"
mkdir -p "$ROOT_DIR/home"
mkdir -p "$ROOT_DIR/jobs"

# Copy services directory if it exists in current directory
if [ -d "services" ]; then
    echo "Copying services directory and its contents..."
    cp -r services "$ROOT_DIR/opt/magellon/"
    echo "Services directory copied successfully"
else
    echo "Warning: 'services' directory not found in current location"
    echo "Make sure to manually copy any required data files"
fi

# Set permissions to 777 recursively
chmod -R 777 "$ROOT_DIR/opt"
chmod -R 777 "$ROOT_DIR/gpfs"
chmod -R 777 "$ROOT_DIR/home"
chmod -R 777 "$ROOT_DIR/jobs"

echo "Directory structure created with permissions 777"

# Check if we're in the right directory (where docker-compose.yml is)
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found in current directory."
    echo "Please run this script from the directory containing docker-compose.yml"
    exit 1
fi

# Make sure the .env file exists and update it
if [ ! -f ".env" ]; then
    echo "Error: .env file not found."
    echo "Please make sure .env file exists in the current directory"
    exit 1
else
    # Update .env file with the new paths
    echo "Updating .env file with correct paths..."
    # Create a backup of the original .env file
    cp .env .env.backup
    
    # Update paths in .env file
    sed -i "s|MAGELLON_HOME_PATH=.*|MAGELLON_HOME_PATH=$ROOT_DIR/home|g" .env
    sed -i "s|MAGELLON_GPFS_PATH=.*|MAGELLON_GPFS_PATH=$ROOT_DIR/gpfs|g" .env
    sed -i "s|MAGELLON_JOBS_PATH=.*|MAGELLON_JOBS_PATH=$ROOT_DIR/jobs|g" .env
    
    echo ".env file updated successfully (backup created as .env.backup)"
fi

# Start Docker Compose
echo "Starting Docker containers..."
docker-compose up -d

echo "Setup complete! Magellon services should now be running."
echo "You can check container status with 'docker-compose ps'"

# Wait for services to start
echo "Waiting for services to start up (15 seconds)..."
sleep 15

# Step 4: Open browser with links
echo "Opening browser links to Magellon services..."
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

echo "Setup process completed!"

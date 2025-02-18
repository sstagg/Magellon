#!/bin/bash

# Step 1: Start Docker Compose
if command -v docker-compose &> /dev/null; then
    DOCKER_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_CMD="docker compose"
else
    echo "Neither 'docker-compose' nor 'docker compose' is available in the PATH."
    exit 1
fi

echo "Using command: $DOCKER_CMD"

$DOCKER_CMD --profile default up -d

# Step 2: Wait for services to be ready (optional)
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




# Step 3: Open browser with links
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

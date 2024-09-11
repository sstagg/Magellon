#!/bin/bash

# Step 1: Start Docker Compose
docker-compose up -d

# Step 2: Wait for services to be ready (optional)
# You can add a sleep here to give the services some time to start, or use a more sophisticated health check
sleep 15

# Step 3: Open browser with links
# Replace the URL with the desired URL for your service
if which xdg-open > /dev/null
then
  xdg-open "http://localhost:8080"
  xdg-open "http://localhost:8000"
  xdg-open "http://localhost:15672"
elif which gnome-open > /dev/null
then
  gnome-open "http://localhost:8080"
  gnome-open "http://localhost:8000"
  gnome-open "http://localhost:15672"
elif which open > /dev/null    # For macOS
then
  open "http://localhost:8080"
  open "http://localhost:8000"
  open "http://localhost:15672"
fi

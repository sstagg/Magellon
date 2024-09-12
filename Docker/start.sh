#!/bin/bash

rm -rf ./mysql/data/*
rm -rf ./consul/data/*

# Step 1: Start Docker Compose
docker-compose --profile default up -d

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
  xdg-open "http://localhost:15672"
  xdg-open "http://localhost:8500"
  xdg-open "http://localhost:3000"
elif which gnome-open > /dev/null
then
  gnome-open "http://localhost:8080/en/panel/images"
  gnome-open "http://localhost:8000"
  gnome-open "http://localhost:15672"
  gnome-open "http://localhost:8500"
  gnome-open "http://localhost:3000"
elif which open > /dev/null    # For macOS
then
  open "http://localhost:8080/en/panel/images"
  open "http://localhost:8000"
  open "http://localhost:15672"
  open "http://localhost:8500"
  open "http://localhost:3000"
fi

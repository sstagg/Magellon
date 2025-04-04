#!/bin/bash
# Define paths and directories
set -e
if [ $# -ne 1 ]; then
    echo "Usage: $0 <root_directory> "
    echo "  Example: $0 /home/user/magellon"
    exit 1
fi
PARENT_DIR=$1
TARGET_DIRS=("services" "jobs" "gpfs" "home")
# 1. Stop and remove Docker containers/networks
docker compose down
# 2. Delete target directories using Docker
for dir in "${TARGET_DIRS[@]}"; do
  docker run --rm -v "${PARENT_DIR}:/parent" alpine \
    sh -c "rm -rf /parent/${dir}" && echo "Deleted ${dir} directory"
done
# 3. Optional: Remove all Docker artifacts
docker system prune -af

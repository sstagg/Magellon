import os
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, ValidationError


class InstallationData(BaseModel):
    # Installation type
    installation_type: Optional[str] = "demo"  # demo or production

    # Single computer installation
    core_service_server_ip: Optional[str] = "127.0.0.1"
    core_service_server_username: Optional[str] = None
    core_service_server_password: Optional[str] = None
    core_service_server_base_directory: Optional[str] = "/opt/magellon"
    core_service_server_port: Optional[int] = 8000

    # Network deployment
    if_install_network: Optional[bool] = False
    webapp_server_ip: Optional[str] = "127.0.0.1"
    webapp_server_username: Optional[str] = None
    webapp_server_password: Optional[str] = None
    webapp_port: Optional[int] = 8080
    worker_nodes: Optional[str] = None  # Comma-separated list of worker IP addresses

    # Cloud deployment
    if_install_cloud: Optional[bool] = False
    cloud_provider: Optional[str] = None  # aws, gcp, azure
    cloud_region: Optional[str] = None
    cloud_access_key: Optional[str] = None
    cloud_secret_key: Optional[str] = None
    cloud_instance_type: Optional[str] = None

    # Database settings
    if_install_mysql: Optional[bool] = True
    mysql_server_ip: Optional[str] = "localhost"
    mysql_server_username: Optional[str] = "root"
    mysql_server_password: Optional[str] = None
    mysql_server_db_username: Optional[str] = "magellon_user"
    mysql_server_db_password: Optional[str] = "behd1d2"
    mysql_server_db_dbname: Optional[str] = "magellon01"
    mysql_server_db_port_no: Optional[int] = 3306

    # RabbitMQ settings
    if_install_rabbitmq: Optional[bool] = True
    rabbitmq_username: Optional[str] = "rabbit"
    rabbitmq_password: Optional[str] = "behd1d2"
    rabbitmq_port: Optional[int] = 5672
    rabbitmq_management_port: Optional[int] = 15672

    # Consul settings
    if_install_consul: Optional[bool] = True
    consul_port: Optional[int] = 8500

    # Prometheus and Grafana
    if_install_prometheus: Optional[bool] = True
    if_install_grafana: Optional[bool] = True
    grafana_username: Optional[str] = "admin"
    grafana_password: Optional[str] = "behd1d2"

    # Frontend and Backend
    if_install_frontend: Optional[bool] = True
    if_install_backend: Optional[bool] = True

    # Plugins
    if_install_result_plugin: Optional[bool] = True
    if_install_ctf_plugin: Optional[bool] = True
    if_install_motioncor_plugin: Optional[bool] = True
    result_plugin_port: Optional[int] = 8030
    ctf_plugin_port: Optional[int] = 8035
    motioncor_plugin_port: Optional[int] = 8036

    # Requirements check results
    requirements_check: Optional[Dict[str, Any]] = None

    def save_settings(self, file_path: str) -> None:
        """Save the installation data to a JSON file."""
        with open(file_path, 'w') as file:
            file.write(self.model_dump_json(indent=2))

        print(f"Settings saved to {file_path}")

    @classmethod
    def load_settings(cls, file_path: str) -> 'InstallationData':
        """Load installation data from a JSON file."""
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                settings_json = file.read()
            try:
                return cls.model_validate_json(settings_json)
            except ValidationError as e:
                print(f"Error validating settings: {e}")
                return cls()
        else:
            print(f"Settings file {file_path} not found, using defaults")
            return cls()

    def generate_env_file(self, output_path: str = ".env") -> bool:
        """Generate .env file for Docker Compose."""
        try:
            env_content = f"""# Paths
MAGELLON_HOME_PATH={self.core_service_server_base_directory}/home
MAGELLON_GPFS_PATH={self.core_service_server_base_directory}/gpfs
MAGELLON_JOBS_PATH={self.core_service_server_base_directory}/jobs

# MySQL Database Configuration
MYSQL_DATABASE={self.mysql_server_db_dbname}
MYSQL_ROOT_PASSWORD={self.mysql_server_db_password}
MYSQL_USER={self.mysql_server_db_username}
MYSQL_PASSWORD={self.mysql_server_db_password}
MYSQL_PORT={self.mysql_server_db_port_no}

# RabbitMQ Configuration
RABBITMQ_DEFAULT_USER={self.rabbitmq_username}
RABBITMQ_DEFAULT_PASS={self.rabbitmq_password}
RABBITMQ_PORT={self.rabbitmq_port}
RABBITMQ_MANAGEMENT_PORT={self.rabbitmq_management_port}

GRAFANA_USER_NAME={self.grafana_username}
GRAFANA_USER_PASS={self.grafana_password}

CONSUL_PORT={self.consul_port}

MAGELLON_FRONTEND_PORT={self.webapp_port}
MAGELLON_BACKEND_PORT={self.core_service_server_port}

MAGELLON_RESULT_PLUGIN_PORT={self.result_plugin_port}
MAGELLON_CTF_PLUGIN_PORT={self.ctf_plugin_port}
MAGELLON_MOTIONCOR_PLUGIN_PORT={self.motioncor_plugin_port}
"""

            with open(output_path, 'w') as file:
                file.write(env_content)

            return True
        except Exception as e:
            print(f"Error generating .env file: {e}")
            return False

    def generate_setup_script(self, output_path: str = "setup-magellon.sh") -> bool:
        """Generate the installation script."""
        try:
            script_content = f"""#!/bin/bash

# Magellon setup script
# This script creates the directory structure for Magellon,
# copies services data, updates .env file, and starts Docker containers

set -e  # Exit immediately if a command exits with non-zero status

ROOT_DIR="{self.core_service_server_base_directory}"
echo "=== Magellon Setup ==="
echo "Setting up Magellon in: $ROOT_DIR"

# Function to log messages
log() {{
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}}

# Function to check command existence
check_command() {{
    if ! command -v $1 &> /dev/null; then
        log "ERROR: '$1' command not found. Please install it first."
        echo "  Suggestion: sudo apt-get update && sudo apt-get install -y $1"
        exit 1
    fi
}}

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
    cp -r services "$ROOT_DIR/services/"
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
find "$ROOT_DIR/services" -type d -exec chmod 755 {{}} \\; 2>/dev/null || log "WARNING: Some permission changes failed"
find "$ROOT_DIR/services" -type f -exec chmod 644 {{}} \\; 2>/dev/null || log "WARNING: Some permission changes failed"
# Set 777 only where absolutely necessary (for shared directories)
chmod -R 777 "$ROOT_DIR/gpfs" 2>/dev/null || log "WARNING: Failed to set permissions on gpfs directory"
chmod -R 777 "$ROOT_DIR/home" 2>/dev/null || log "WARNING: Failed to set permissions on home directory"
chmod -R 777 "$ROOT_DIR/jobs" 2>/dev/null || log "WARNING: Failed to set permissions on jobs directory"

log "Directory structure created with appropriate permissions"

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
log "  - http://{self.core_service_server_ip}:{self.webapp_port}/en/panel/images"
log "  - http://{self.core_service_server_ip}:{self.core_service_server_port}"

# Check if this is an interactive environment with a desktop
if [ -n "$DISPLAY" ]; then
    log "Attempting to open browser links..."
    if which xdg-open > /dev/null; then
        xdg-open "http://{self.core_service_server_ip}:{self.webapp_port}/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        xdg-open "http://{self.core_service_server_ip}:{self.core_service_server_port}" 2>/dev/null || log "Could not open browser automatically"
    elif which gnome-open > /dev/null; then
        gnome-open "http://{self.core_service_server_ip}:{self.webapp_port}/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        gnome-open "http://{self.core_service_server_ip}:{self.core_service_server_port}" 2>/dev/null || log "Could not open browser automatically"
    elif which open > /dev/null; then    # For macOS
        open "http://{self.core_service_server_ip}:{self.webapp_port}/en/panel/images" 2>/dev/null || log "Could not open browser automatically"
        open "http://{self.core_service_server_ip}:{self.core_service_server_port}" 2>/dev/null || log "Could not open browser automatically"
    else
        log "No compatible browser opener found. Please open the URLs manually."
    fi
else
    log "Running in non-graphical environment. Please access URLs from a browser manually."
fi

log "=== Setup process completed! ==="
"""

            with open(output_path, 'w') as file:
                file.write(script_content)

            # Make the script executable
            os.chmod(output_path, 0o755)

            return True
        except Exception as e:
            print(f"Error generating setup script: {e}")
            return False

    def generate_inventory_file(self, output_path: str = "inventory.ini") -> bool:
        """Generate Ansible inventory file for remote installation."""
        try:
            inventory_content = f"""[magellon_master]
{self.core_service_server_ip} ansible_user={self.core_service_server_username} ansible_password={self.core_service_server_password} ansible_sudo_pass={self.core_service_server_password}
"""

            # Add workers if network installation is enabled
            if self.if_install_network and self.worker_nodes:
                inventory_content += "\n[magellon_workers]\n"
                for worker in self.worker_nodes.split(','):
                    inventory_content += f"{worker.strip()} ansible_user={self.webapp_server_username} ansible_password={self.webapp_server_password} ansible_sudo_pass={self.webapp_server_password}\n"

            with open(output_path, 'w') as file:
                file.write(inventory_content)

            return True
        except Exception as e:
            print(f"Error generating inventory file: {e}")
            return False
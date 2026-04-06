"""
Docker-related utilities for Magellon Installer.

This module provides functions to check Docker installation, manage containers,
and verify Docker-related dependencies.
"""

import os
import subprocess
import logging
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union

logger = logging.getLogger(__name__)


def check_docker_installation() -> Tuple[bool, str]:
    """
    Check if Docker is installed and running.

    Returns:
        Tuple[bool, str]: A tuple containing:
            - Boolean indicating if Docker is properly installed and running
            - String with version information or error message
    """
    try:
        # Check if docker command exists
        result = subprocess.run(
            ["docker", "--version"],
            check=True,
            capture_output=True,
            text=True
        )
        version_info = result.stdout.strip()

        # Check if Docker daemon is running
        result = subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            text=True
        )

        return True, version_info
    except subprocess.SubprocessError as e:
        if e.returncode == 127:  # Command not found
            return False, "Docker is not installed"
        else:
            return False, f"Docker is installed but not running or permission issues: {str(e)}"
    except Exception as e:
        return False, f"Error checking Docker: {str(e)}"


def check_docker_compose() -> Tuple[bool, str, str]:
    """
    Check which version of Docker Compose is available.

    Returns:
        Tuple[bool, str, str]: A tuple containing:
            - Boolean indicating if Docker Compose is available
            - The command to use for Docker Compose
            - Version information or error message
    """
    # First try Docker Compose V2 (plugin)
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True
        )
        return True, "docker compose", result.stdout.strip()
    except subprocess.SubprocessError:
        # Try Docker Compose V1 (standalone)
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "docker-compose", result.stdout.strip()
        except subprocess.SubprocessError:
            return False, "", "Docker Compose not found"


def check_nvidia_docker() -> Tuple[bool, str]:
    """
    Check if NVIDIA Container Toolkit is installed and configured.

    Returns:
        Tuple[bool, str]: A tuple containing:
            - Boolean indicating if NVIDIA Docker support is available
            - String with result information or error message
    """
    # Skip check if docker is not available
    docker_available, docker_msg = check_docker_installation()
    if not docker_available:
        return False, f"Docker not available: {docker_msg}"

    # Simple test image to check NVIDIA Docker
    test_image = "nvidia/cuda:12.1.0-base-ubuntu22.04"

    try:
        # Try to run nvidia-smi inside a container
        result = subprocess.run(
            ["docker", "run", "--rm", "--gpus", "all", test_image, "nvidia-smi"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return True, "NVIDIA Container Toolkit is properly configured"
    except subprocess.SubprocessError as e:
        if "Unknown runtime specified" in str(e) or "Error response from daemon" in str(e):
            return False, "NVIDIA Container Toolkit not installed or configured"
        elif "could not select device driver" in str(e.stderr if hasattr(e, 'stderr') else ""):
            return False, "NVIDIA Container Toolkit installed but GPU drivers not available"
        else:
            return False, f"Failed to run NVIDIA container: {str(e)}"
    except Exception as e:
        return False, f"Error checking NVIDIA Docker support: {str(e)}"


def get_running_containers() -> List[Dict[str, Any]]:
    """
    Get list of running Docker containers.

    Returns:
        List[Dict[str, Any]]: List of container information dictionaries
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{json .}}"],
            check=True,
            capture_output=True,
            text=True
        )

        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return containers
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to get running containers: {str(e)}")
        return []


def execute_docker_compose(compose_command: str, args: List[str], cwd: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Execute a Docker Compose command.

    Args:
        compose_command: The Docker Compose command (e.g., "docker compose" or "docker-compose")
        args: List of arguments to pass to the command
        cwd: Working directory for the command

    Returns:
        Tuple[bool, str]: Success status and output/error message
    """
    cmd_parts = compose_command.split() + args

    try:
        result = subprocess.run(
            cmd_parts,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return True, result.stdout
    except subprocess.SubprocessError as e:
        error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
        return False, f"Docker Compose command failed: {error_msg}"


def wait_for_container_health(container_name: str, timeout: int = 60) -> bool:
    """
    Wait for a container to become healthy.

    Args:
        container_name: Name of the container to check
        timeout: Maximum time to wait in seconds

    Returns:
        bool: True if container becomes healthy, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
                check=True,
                capture_output=True,
                text=True
            )
            status = result.stdout.strip()

            if status == "healthy":
                return True
            elif status == "unhealthy":
                logger.warning(f"Container {container_name} is unhealthy")
                return False

            # Still starting up, wait a bit
            time.sleep(2)
        except subprocess.SubprocessError:
            # Container might not exist yet or doesn't have health check
            time.sleep(2)

    logger.warning(f"Timeout waiting for {container_name} to become healthy")
    return False


def check_container_logs(container_name: str, max_lines: int = 100) -> str:
    """
    Get the logs from a container.

    Args:
        container_name: Name of the container
        max_lines: Maximum number of lines to return

    Returns:
        str: Container logs or error message
    """
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(max_lines), container_name],
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    except subprocess.SubprocessError as e:
        return f"Failed to get logs for {container_name}: {str(e)}"


def get_host_ports_for_service(compose_file: Path, service_name: str) -> List[Tuple[str, str]]:
    """
    Get the host ports mapped for a service in the docker-compose file.

    Args:
        compose_file: Path to the docker-compose.yml file
        service_name: Name of the service

    Returns:
        List[Tuple[str, str]]: List of (host_port, container_port) tuples
    """
    try:
        # This is a simplistic approach - for a more robust solution, use a YAML parser
        with open(compose_file, 'r') as f:
            content = f.read()

        # Find the service section
        service_pattern = rf"{service_name}:\s*\n"
        match = re.search(service_pattern, content)
        if not match:
            return []

        # Find the ports section
        service_start = match.end()
        next_service = re.search(r"\n\s*\w+:\s*\n", content[service_start:])
        service_end = next_service.start() + service_start if next_service else len(content)
        service_content = content[service_start:service_end]

        # Extract ports
        ports_pattern = r'ports:\s*\n(\s*-\s*"?([^:]+):([^"]+)"?\s*\n)+'
        ports_match = re.search(ports_pattern, service_content)
        if not ports_match:
            return []

        # Parse each port mapping
        port_mappings = []
        port_lines = re.finditer(r'\s*-\s*"?([^:]+):([^"\n]+)"?\s*\n', service_content)
        for line in port_lines:
            if len(line.groups()) >= 2:
                host_port, container_port = line.groups()
                port_mappings.append((host_port.strip(), container_port.strip()))

        return port_mappings
    except Exception as e:
        logger.error(f"Error parsing docker-compose file for ports: {str(e)}")
        return []
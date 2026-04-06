"""
Magellon Installer Library

This package contains the modules needed for installing and configuring
the Magellon system.
"""

from .config import (
    MagellonConfig, CudaConfig, DockerInfo,
    DatabaseConfig, RabbitMQConfig, GrafanaConfig, ServicePorts
)
from .installer import MagellonInstaller
from .validator import GPUValidator
from .services import ServiceManager
from .utils import (
    setup_logging, detect_cuda_version, generate_secure_password,
    check_docker_compose_version, verify_file_exists, copy_directory,
    is_running_as_admin
)
from .docker import (
    check_docker_installation, check_docker_compose, check_nvidia_docker,
    get_running_containers, execute_docker_compose, wait_for_container_health,
    check_container_logs, get_host_ports_for_service
)

__version__ = '1.0.0'
"""
Configuration models for Magellon Installer using Pydantic.

This module defines the data models that represent configuration settings
for various components of the Magellon system.
"""

import re
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, validator

# CUDA version mappings from supported CUDA versions to appropriate Docker images and MotionCor binaries
CUDA_MAPPING = {
    "11.1.1": {
        "image": "nvidia/cuda:11.1.1-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda111_Mar312023"
    },
    "11.2": {
        "image": "nvidia/cuda:11.2.2-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda112_Mar312023"
    },
    "11.3": {
        "image": "nvidia/cuda:11.3.1-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda113_Mar312023"
    },
    "11.4": {
        "image": "nvidia/cuda:11.4.3-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda114_Mar312023"
    },
    "11.5": {
        "image": "nvidia/cuda:11.5.2-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda115_Mar312023"
    },
    "11.6": {
        "image": "nvidia/cuda:11.6.1-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda116_Mar312023"
    },
    "11.7": {
        "image": "nvidia/cuda:11.7.1-devel-ubuntu20.04",
        "motioncor": "MotionCor2_1.6.4_Cuda117_Mar312023"
    },
    "11.8": {
        "image": "nvidia/cuda:11.8.0-devel-ubuntu22.04",
        "motioncor": "MotionCor2_1.6.4_Cuda118_Mar312023"
    },
    "12.1": {
        "image": "nvidia/cuda:12.1.0-devel-ubuntu22.04",
        "motioncor": "MotionCor2_1.6.4_Cuda121_Mar312023"
    }
}


class DockerInfo(BaseModel):
    """Information about Docker installation and commands"""
    docker_command: str = "docker"
    compose_command: str = "docker compose"

    @validator('compose_command')
    def validate_compose_command(cls, v, values):
        """Validate that docker compose command works, otherwise fall back to docker-compose"""
        try:
            # Check if the Docker Compose V2 format works
            cmd_parts = v.split()
            if len(cmd_parts) >= 2:
                subprocess.run([cmd_parts[0], cmd_parts[1], "version"],
                               check=True, capture_output=True, text=True)
                return v
        except (subprocess.SubprocessError, IndexError):
            # Try the older docker-compose command
            try:
                subprocess.run(["docker-compose", "version"],
                               check=True, capture_output=True, text=True)
                return "docker-compose"
            except subprocess.SubprocessError:
                raise ValueError("Neither docker compose nor docker-compose found")
        return v


class CudaConfig(BaseModel):
    """Configuration for CUDA and GPU requirements"""
    cuda_version: str
    cuda_image: str = ""
    motioncor_binary: str = ""

    @validator('cuda_version')
    def validate_cuda_version(cls, v):
        """Validate that the CUDA version is supported"""
        # Strip minor version if present (e.g., 11.8.0 -> 11.8)
        v_parts = v.split('.')
        if len(v_parts) > 2:
            v = '.'.join(v_parts[:2])

        # Special case for 11.1.1
        if v == "11.1" and len(v_parts) > 2 and v_parts[2] != "0":
            v = "11.1.1"

        if v not in CUDA_MAPPING:
            supported = ", ".join(CUDA_MAPPING.keys())
            raise ValueError(f"Unsupported CUDA version: {v}. Supported versions: {supported}")
        return v

    def get_cuda_info(self) -> Tuple[str, str]:
        """Get the CUDA image and MotionCor binary based on version"""
        self.cuda_image = CUDA_MAPPING[self.cuda_version]["image"]
        self.motioncor_binary = CUDA_MAPPING[self.cuda_version]["motioncor"]
        return self.cuda_image, self.motioncor_binary


class DatabaseConfig(BaseModel):
    """Configuration for MySQL database"""
    database: str = "magellon01"
    root_password: str = "behd1d2"  # Should be randomized in production
    user: str = "magellon_user"
    password: str = "behd1d2"  # Should be randomized in production
    port: int = 3306


class RabbitMQConfig(BaseModel):
    """Configuration for RabbitMQ"""
    user: str = "rabbit"
    password: str = "behd1d2"  # Should be randomized in production
    port: int = 5672
    management_port: int = 15672


class GrafanaConfig(BaseModel):
    """Configuration for Grafana"""
    user: str = "admin"
    password: str = "behd1d2"  # Should be randomized in production
    port: int = 3000


class ServicePorts(BaseModel):
    """Ports for various Magellon services"""
    consul_port: int = 8500
    frontend_port: int = 8080
    backend_port: int = 8000
    result_plugin_port: int = 8030
    ctf_plugin_port: int = 8035
    motioncor_plugin_port: int = 8036


class MagellonConfig(BaseModel):
    """Main configuration for Magellon installation"""
    root_dir: Path
    cuda_config: CudaConfig
    docker_info: DockerInfo = Field(default_factory=DockerInfo)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    grafana: GrafanaConfig = Field(default_factory=GrafanaConfig)
    service_ports: ServicePorts = Field(default_factory=ServicePorts)

    # Required directory structure for Magellon
    required_directories: List[str] = [
        "services/mysql/data",
        "services/mysql/conf",
        "services/mysql/init",
        "services/consul/data",
        "services/consul/config",
        "services/prometheus",
        "gpfs",
        "home",
        "jobs"
    ]

    @validator('root_dir')
    def validate_root_dir(cls, v):
        """Validate that the root directory is absolute"""
        v = Path(v).resolve()
        if not v.is_absolute():
            raise ValueError(f"Root directory must be an absolute path: {v}")
        return v

    def get_paths(self) -> Dict[str, str]:
        """Get all the paths needed for environment variables"""
        return {
            "MAGELLON_HOME_PATH": str(self.root_dir / "home"),
            "MAGELLON_GPFS_PATH": str(self.root_dir / "gpfs"),
            "MAGELLON_JOBS_PATH": str(self.root_dir / "jobs"),
            "MAGELLON_ROOT_DIR": str(self.root_dir)
        }

    def get_directory_paths(self) -> List[Path]:
        """Get full paths for all required directories"""
        return [self.root_dir / dir_path for dir_path in self.required_directories]

    def get_env_variables(self) -> Dict[str, str]:
        """Get all environment variables for the .env file"""
        # Get CUDA image and MotionCor binary
        cuda_image, motioncor_binary = self.cuda_config.get_cuda_info()

        # Prepare environment variables
        return {
            # Paths
            **self.get_paths(),
            "CUDA_IMAGE": cuda_image,
            "MOTIONCOR_BINARY": motioncor_binary,

            # MySQL
            "MYSQL_DATABASE": self.database.database,
            "MYSQL_ROOT_PASSWORD": self.database.root_password,
            "MYSQL_USER": self.database.user,
            "MYSQL_PASSWORD": self.database.password,
            "MYSQL_PORT": str(self.database.port),

            # RabbitMQ
            "RABBITMQ_DEFAULT_USER": self.rabbitmq.user,
            "RABBITMQ_DEFAULT_PASS": self.rabbitmq.password,
            "RABBITMQ_PORT": str(self.rabbitmq.port),
            "RABBITMQ_MANAGEMENT_PORT": str(self.rabbitmq.management_port),

            # Grafana
            "GRAFANA_USER_NAME": self.grafana.user,
            "GRAFANA_USER_PASS": self.grafana.password,

            # Service ports
            "CONSUL_PORT": str(self.service_ports.consul_port),
            "MAGELLON_FRONTEND_PORT": str(self.service_ports.frontend_port),
            "MAGELLON_BACKEND_PORT": str(self.service_ports.backend_port),
            "MAGELLON_RESULT_PLUGIN_PORT": str(self.service_ports.result_plugin_port),
            "MAGELLON_CTF_PLUGIN_PORT": str(self.service_ports.ctf_plugin_port),
            "MAGELLON_MOTIONCOR_PLUGIN_PORT": str(self.service_ports.motioncor_plugin_port),
        }
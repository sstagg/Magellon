"""
GPU Environment Validation Module for Magellon.

This module provides functionality to validate the GPU computing environment
including NVIDIA drivers, CUDA toolkit, and NVIDIA Container Toolkit.
"""

import os
import sys
import subprocess
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class GPUValidator:
    """Class to validate GPU environment for Magellon"""

    def __init__(self, required_cuda_version: str = "11.8", quiet: bool = False, ignore_warnings: bool = False):
        """
        Initialize the GPU validator.

        Args:
            required_cuda_version: Minimum required CUDA version
            quiet: If True, only output errors, no progress information
            ignore_warnings: If True, continue even if non-critical warnings are found
        """
        self.required_cuda_version = required_cuda_version
        self.quiet = quiet
        self.ignore_warnings = ignore_warnings
        self.docker_test_image = f"nvidia/cuda:{required_cuda_version}.0-base-ubuntu22.04"
        self.exit_code = 0

    def log(self, level: str, message: str) -> None:
        """
        Log a message with the appropriate level.

        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Message to log
        """
        # Always log to the logger
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)

        # Only print to stdout if not in quiet mode or if it's an error
        if not self.quiet or level == "ERROR":
            print(f"[{level}] {message}")

    def run_command(self, cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
        """
        Run a command and return exit code, stdout, and stderr.

        Args:
            cmd: Command to run as a list of strings
            check: Whether to raise an exception on non-zero exit code

        Returns:
            Tuple[int, str, str]: Exit code, stdout, and stderr
        """
        try:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        except subprocess.SubprocessError as e:
            return e.returncode if hasattr(e, 'returncode') else 1, "", str(e)

    def version_compare(self, version1: str, version2: str) -> bool:
        """
        Compare version strings.

        Args:
            version1: First version string
            version2: Second version string

        Returns:
            bool: True if version1 >= version2, False otherwise
        """
        v1_parts = [int(x) for x in version1.split(".")]
        v2_parts = [int(x) for x in version2.split(".")]

        # Pad with zeros if needed
        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)

        # Compare parts
        for i in range(3):
            if v1_parts[i] < v2_parts[i]:
                return False
            if v1_parts[i] > v2_parts[i]:
                return True

        # Equal versions
        return True

    def check_prerequisites(self) -> bool:
        """
        Check system prerequisites.

        Returns:
            bool: True if prerequisites are met, False otherwise
        """
        self.log("INFO", "Checking system prerequisites...")

        # Check if we have required utilities
        for cmd in ["grep", "sed", "awk"]:
            returncode, _, _ = self.run_command(["which", cmd], check=False)
            if returncode != 0:
                self.log("ERROR", f"Required utility '{cmd}' not found. Please install it and try again.")
                self.exit_code = 10
                return False

        return True

    def check_nvidia_driver(self) -> bool:
        """
        Check NVIDIA driver installation.

        Returns:
            bool: True if drivers are properly installed, False otherwise
        """
        self.log("INFO", "Checking NVIDIA drivers...")

        # Check if nvidia-smi is available
        returncode, _, _ = self.run_command(["which", "nvidia-smi"], check=False)
        if returncode != 0:
            self.log("ERROR", "nvidia-smi not found. NVIDIA drivers may not be installed.")
            self.exit_code = 1
            return False

        # Get driver version
        returncode, stdout, _ = self.run_command(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=False
        )

        if returncode != 0 or not stdout.strip():
            self.log("ERROR", "Failed to get NVIDIA driver version.")
            self.exit_code = 1
            return False

        driver_version = stdout.strip().split("\n")[0]
        self.log("INFO", f"NVIDIA driver version: {driver_version}")

        # Check if GPUs are visible
        returncode, stdout, _ = self.run_command(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            check=False
        )

        if returncode != 0:
            self.log("ERROR", "Error querying GPU names.")
            self.exit_code = 1
            return False

        gpu_names = stdout.strip().split("\n")
        gpu_count = len([name for name in gpu_names if name])

        if gpu_count == 0:
            self.log("ERROR", "No NVIDIA GPUs detected by nvidia-smi.")
            self.exit_code = 1
            return False

        self.log("INFO", f"Detected {gpu_count} NVIDIA GPU(s):")
        for gpu_name in gpu_names:
            if gpu_name:
                self.log("INFO", f"  - {gpu_name}")

        # Check GPU health
        returncode, _, _ = self.run_command(["nvidia-smi"], check=False)
        if returncode != 0:
            self.log("ERROR", "nvidia-smi reports GPU errors. GPUs may be in a bad state.")
            self.exit_code = 1
            return False

        return True

    def check_cuda(self) -> bool:
        """
        Check CUDA installation.

        Returns:
            bool: True if CUDA is properly installed and meets version requirements,
                 False otherwise
        """
        self.log("INFO", "Checking CUDA installation...")

        # Check if nvcc is available
        returncode, _, _ = self.run_command(["which", "nvcc"], check=False)
        if returncode != 0:
            self.log("WARNING", "nvcc not found. CUDA may not be installed or not in PATH.")
            self.log("INFO", "If CUDA is installed, check the PATH or load the CUDA module.")

            # This is a warning, not an error, as CUDA may be available in Docker
            if not self.ignore_warnings:
                self.exit_code = 2
                return False
            return True

        # Get CUDA version
        returncode, stdout, _ = self.run_command(["nvcc", "--version"], check=False)
        if returncode != 0:
            self.log("ERROR", "Failed to run nvcc --version.")
            self.exit_code = 2
            return False

        # Extract version using regex
        match = re.search(r"release (\d+\.\d+)", stdout)
        if not match:
            self.log("ERROR", "Failed to determine CUDA version.")
            self.exit_code = 2
            return False

        cuda_version = match.group(1)
        self.log("INFO", f"CUDA version: {cuda_version}")

        # Compare CUDA version against minimum requirement
        if not self.version_compare(cuda_version, self.required_cuda_version):
            self.log("ERROR", f"CUDA version is {cuda_version}, but {self.required_cuda_version} or higher is required.")
            self.exit_code = 3
            return False

        # Check CUDA libraries consistency
        ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
        if ld_library_path:
            self.log("INFO", f"LD_LIBRARY_PATH is set: {ld_library_path}")

            # Check if multiple CUDA versions might be in the path
            cuda_paths = [p for p in ld_library_path.split(":") if "cuda" in p]
            cuda_path_count = len(cuda_paths)

            if cuda_path_count > 1:
                self.log("WARNING", "Multiple CUDA library paths detected in LD_LIBRARY_PATH. This might cause version conflicts.")
                if not self.ignore_warnings:
                    self.exit_code = 3
                    return False
        else:
            self.log("WARNING", "LD_LIBRARY_PATH is not set. Some CUDA applications might fail to find libraries.")

        return True

    def check_docker(self) -> bool:
        """
        Check Docker installation and permissions.

        Returns:
            bool: True if Docker is properly installed and configured, False otherwise
        """
        self.log("INFO", "Checking Docker installation...")

        # Check if Docker is installed
        returncode, _, _ = self.run_command(["which", "docker"], check=False)
        if returncode != 0:
            self.log("ERROR", "Docker is not installed.")
            self.exit_code = 4
            return False

        # Get Docker version
        returncode, stdout, _ = self.run_command(["docker", "--version"], check=False)
        if returncode != 0:
            self.log("ERROR", "Failed to get Docker version.")
            self.exit_code = 4
            return False

        docker_version = stdout.strip()
        self.log("INFO", f"Docker version: {docker_version}")

        # Check if Docker daemon is running
        returncode, _, stderr = self.run_command(["docker", "info"], check=False)
        if returncode != 0:
            self.log("ERROR", "Docker is either not running or you don't have permission to access it.")
            self.log("INFO", "Ensure Docker is running and that your user is in the 'docker' group.")
            self.log("INFO", "If needed, run: sudo systemctl start docker")
            self.log("INFO", "To add your user to the docker group: sudo usermod -aG docker $USER")
            self.log("INFO", "Then log out and back in, or run: newgrp docker")
            self.exit_code = 5
            return False

        # Check if user is in docker group
        try:
            result = subprocess.run(["groups"], check=True, capture_output=True, text=True)
            if "docker" not in result.stdout:
                self.log("WARNING", "Current user is not in the 'docker' group. You might be using sudo for Docker commands.")
                if not self.ignore_warnings:
                    self.log("INFO", "To add your user to the docker group: sudo usermod -aG docker $USER")
                    self.log("INFO", "Then log out and back in, or run: newgrp docker")
                    return False
        except subprocess.SubprocessError:
            self.log("WARNING", "Failed to check if user is in docker group.")

        return True

    def check_nvidia_docker(self) -> bool:
        """
        Check NVIDIA Container Toolkit and Docker GPU support.

        Returns:
            bool: True if NVIDIA Docker is properly configured, False otherwise
        """
        self.log("INFO", "Checking NVIDIA Container Toolkit configuration...")

        # Test simple nvidia-smi run in container
        self.log("INFO", "Testing GPU access from Docker container...")
        returncode, _, stderr = self.run_command(
            ["docker", "run", "--rm", "--gpus", "all", self.docker_test_image, "nvidia-smi"],
            check=False
        )

        if returncode != 0:
            self.log("ERROR", "Docker cannot access the GPU.")
            self.log("INFO", "Ensure NVIDIA Container Toolkit is installed:")
            self.log("INFO", "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html")

            # Check for common error messages and provide more specific guidance
            if "Unknown runtime specified" in stderr:
                self.log("INFO", "The NVIDIA runtime is not configured in Docker.")
                self.log("INFO", "Ensure that /etc/docker/daemon.json contains:")
                self.log("INFO", '  {"runtimes": {"nvidia": {"path": "nvidia-container-runtime", "runtimeArgs": []}}}')
                self.log("INFO", "Then restart Docker: sudo systemctl restart docker")
            elif "Could not select device driver" in stderr:
                self.log("INFO", "The NVIDIA Container Runtime could not find the NVIDIA driver.")
                self.log("INFO", "Ensure that the NVIDIA driver is properly installed.")

            self.exit_code = 6
            return False

        # Check nvidia-container-runtime integration
        returncode, stdout, _ = self.run_command(["docker", "info"], check=False)
        if returncode == 0 and "nvidia" not in stdout:
            self.log("WARNING", "NVIDIA runtime not listed in Docker info. NVIDIA Container Toolkit might not be fully integrated.")
            if not self.ignore_warnings:
                self.exit_code = 6
                return False

        # Run more comprehensive test to check GPU capabilities
        self.log("INFO", "Testing CUDA operation in container...")
        returncode, stdout, _ = self.run_command(
            ["docker", "run", "--rm", "--gpus", "all", self.docker_test_image,
             "bash", "-c", "nvidia-smi -L && nvidia-smi -q -d MEMORY"],
            check=False
        )

        if returncode != 0:
            self.log("ERROR", "Failed to run comprehensive GPU test in container.")
            self.exit_code = 6
            return False

        self.log("INFO", "NVIDIA Container Toolkit is properly configured.")
        return True

    def validate(self) -> bool:
        """
        Run all validation checks.

        Returns:
            bool: True if all checks pass, False otherwise
        """
        checks = [
            self.check_prerequisites,
            self.check_nvidia_driver,
            self.check_cuda,
            self.check_docker,
            self.check_nvidia_docker
        ]

        for check in checks:
            if not check():
                return False

        self.log("INFO", "✅ All validation checks passed!")
        return True

    @property
    def status(self) -> int:
        """
        Get the validation status.

        Returns:
            int: Exit code (0 for success, non-zero for failure)
        """
        return self.exit_code
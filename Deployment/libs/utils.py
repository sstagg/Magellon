"""
Utility functions for Magellon Installer.

This module contains helper functions used across the codebase.
"""

import os
import logging
import re
import subprocess
import platform
import random
import string
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any


def setup_logging(log_dir: Optional[Path] = None, log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging for the application.

    Args:
        log_dir: Directory to store log files. If None, logs will go to stdout only.
        log_level: The logging level to use.

    Returns:
        The configured logger instance
    """
    # Create a timestamp for the log filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_format = "[%(asctime)s] [%(levelname)s] %(message)s"

    # Configure the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Always add a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # Add a file handler if log_dir is provided
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"magellon-installer-{timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    return logger


def detect_cuda_version() -> str:
    """
    Detect CUDA version installed on the system.

    Returns:
        str: The detected CUDA version, or a default of "11.8" if not found
    """
    try:
        # Try to get version from nvcc
        result = subprocess.run(
            ["nvcc", "--version"],
            check=True, capture_output=True, text=True
        )
        output = result.stdout

        # Extract version using regex
        match = re.search(r"release (\d+\.\d+)", output)
        if match:
            return match.group(1)
    except (subprocess.SubprocessError, FileNotFoundError):
        # Try with nvidia-smi if nvcc fails
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                check=True, capture_output=True, text=True
            )
            # Extract CUDA version from nvidia-smi output
            match = re.search(r"CUDA Version: (\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Default to latest supported version if detection fails
    return "11.8"


def generate_secure_password(length: int = 12) -> str:
    """
    Generate a secure random password.

    Args:
        length: The length of the password to generate

    Returns:
        str: A secure random password
    """
    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    # Ensure at least one of each character type
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special)
    ]

    # Fill the rest with a mix of all character types
    all_chars = lowercase + uppercase + digits + special
    password.extend(random.choice(all_chars) for _ in range(length - 4))

    # Shuffle the password characters
    random.shuffle(password)

    return ''.join(password)


def check_docker_compose_version() -> Tuple[str, str]:
    """
    Check which version of Docker Compose is installed.

    Returns:
        Tuple[str, str]: A tuple containing the docker command and compose command
    """
    docker_command = "docker"

    # First, check if Docker is installed
    try:
        subprocess.run([docker_command, "--version"], check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        raise RuntimeError("Docker is not installed or not in the PATH")

    # Try Docker Compose V2 (plugin-based)
    try:
        subprocess.run([docker_command, "compose", "version"], check=True, capture_output=True)
        return docker_command, "docker compose"
    except subprocess.SubprocessError:
        # Try Docker Compose V1 (standalone binary)
        try:
            subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
            return docker_command, "docker-compose"
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError("Docker Compose is not installed")


def verify_file_exists(filepath: Path, error_msg: str = None) -> bool:
    """
    Verify that a file exists.

    Args:
        filepath: The file path to check
        error_msg: Optional custom error message

    Returns:
        bool: True if the file exists, False otherwise

    Raises:
        FileNotFoundError: If the file does not exist and error_msg is provided
    """
    if filepath.is_file():
        return True

    if error_msg:
        raise FileNotFoundError(error_msg)
    return False


def copy_directory(src: Path, dst: Path, overwrite: bool = False) -> bool:
    """
    Copy a directory and its contents.

    Args:
        src: Source directory
        dst: Destination directory
        overwrite: Whether to overwrite existing files

    Returns:
        bool: True if the copy was successful, False otherwise
    """
    try:
        if not src.exists():
            return False

        if not dst.exists():
            dst.mkdir(parents=True, exist_ok=True)

        # On Windows, use a recursive approach to avoid issues with shutil.copytree
        if platform.system() == "Windows":
            def _copy_tree(src_dir, dst_dir):
                for item in src_dir.iterdir():
                    if item.is_dir():
                        new_dst = dst_dir / item.name
                        new_dst.mkdir(exist_ok=True)
                        _copy_tree(item, new_dst)
                    else:
                        dst_file = dst_dir / item.name
                        if not dst_file.exists() or overwrite:
                            shutil.copy2(item, dst_file)

            _copy_tree(src, dst)
        else:
            # Use copytree for Unix systems with dirs_exist_ok (Python 3.8+)
            import shutil
            shutil.copytree(src, dst, dirs_exist_ok=True)

        return True
    except Exception as e:
        logging.error(f"Error copying directory {src} to {dst}: {e}")
        return False


def is_running_as_admin() -> bool:
    """
    Check if the script is running with administrative privileges.

    Returns:
        bool: True if running as admin/root, False otherwise
    """
    if platform.system() == "Windows":
        try:
            # Check if the script can write to a system directory
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        # On Unix, check if UID is 0 (root)
        return os.geteuid() == 0
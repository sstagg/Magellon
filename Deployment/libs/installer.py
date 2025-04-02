"""
Core installer functionality for Magellon.

This module handles the actual installation process, including setting up
directories, configuring services, and starting Docker containers.
"""

import os
import sys
import time
import shutil
import logging
import subprocess
import platform
import webbrowser
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from jinja2 import Environment, FileSystemLoader

from .config import MagellonConfig
from .utils import setup_logging

logger = logging.getLogger(__name__)


class MagellonInstaller:
    """Class to handle the installation of Magellon"""

    def __init__(self, config: MagellonConfig):
        """
        Initialize the installer with a configuration.

        Args:
            config: The MagellonConfig object with all necessary settings
        """
        self.config = config
        self.env_vars = {}

        # Setup Jinja2 environment for templates
        template_dir = Path(__file__).parent.parent / "assets" / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    def check_prerequisites(self) -> bool:
        """
        Check if all prerequisites are met.

        Returns:
            bool: True if all prerequisites are met, False otherwise
        """
        logger.info("Checking prerequisites...")

        # Check Docker
        try:
            result = subprocess.run(
                [self.config.docker_info.docker_command, "--version"],
                check=True, capture_output=True, text=True
            )
            logger.info(f"Docker installed: {result.stdout.strip()}")
        except subprocess.SubprocessError:
            logger.error("Docker is not installed or not running")
            return False

        # Check NVIDIA GPU support if on Linux
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["nvidia-smi"],
                    check=True, capture_output=True, text=True
                )
                logger.info("NVIDIA GPU detected")
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("NVIDIA GPU drivers not detected. This might be an issue for GPU-dependent features.")
        else:
            logger.warning(f"Running on {platform.system()} - GPU functionality might be limited")

        return True

    def create_directory_structure(self) -> bool:
        """
        Create the required directory structure.

        Returns:
            bool: True if directories were created successfully, False otherwise
        """
        logger.info(f"Creating directory structure in {self.config.root_dir}")

        try:
            # Create all required directories
            for dir_path in self.config.get_directory_paths():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {dir_path}")

            # Set permissions (similar to chmod 777 in bash script)
            if platform.system() != "Windows":
                for dir_path in self.config.get_directory_paths():
                    try:
                        # This is equivalent to chmod 777 in the bash script
                        os.chmod(dir_path, 0o777)
                    except Exception as e:
                        logger.warning(f"Failed to set permissions on {dir_path}: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to create directory structure: {e}")
            return False

    def prepare_env_file(self) -> bool:
        """
        Prepare the .env file with all necessary variables.

        Returns:
            bool: True if the .env file was created successfully, False otherwise
        """
        logger.info("Preparing environment variables")

        try:
            # Get all environment variables
            self.env_vars = self.config.get_env_variables()

            # Create .env file from template
            env_template = self.jinja_env.get_template("env.j2")
            env_content = env_template.render(**self.env_vars)

            env_file = Path.cwd() / ".env"
            env_file.write_text(env_content)
            logger.info(f"Created .env file: {env_file}")

            # Create a backup
            env_backup = Path.cwd() / ".env.backup"
            shutil.copy2(env_file, env_backup)
            logger.info(f"Created backup: {env_backup}")

            return True
        except Exception as e:
            logger.error(f"Failed to prepare .env file: {e}")
            return False

    def copy_service_files(self) -> bool:
        """
        Copy service files if they exist in the current directory.

        Returns:
            bool: True if files were copied successfully or no files to copy,
                 False if an error occurred during copying
        """
        services_dir = Path.cwd() / "services"
        if not services_dir.exists():
            logger.warning("'services' directory not found in current location")
            return True  # Not a failure, just nothing to copy

        logger.info("Copying services directory...")

        dest_services_dir = self.config.root_dir / "services"
        try:
            if platform.system() == "Windows":
                # Windows has issues with shutil.copytree, handle recursively
                def copy_tree(src, dst):
                    if not dst.exists():
                        dst.mkdir(parents=True, exist_ok=True)
                    for item in src.iterdir():
                        dest_item = dst / item.name
                        if item.is_dir():
                            copy_tree(item, dest_item)
                        else:
                            shutil.copy2(item, dest_item)

                copy_tree(services_dir, dest_services_dir)
            else:
                # Use copytree with dirs_exist_ok (Python 3.8+)
                shutil.copytree(services_dir, dest_services_dir, dirs_exist_ok=True)

            logger.info("Services directory copied successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to copy services directory: {e}")
            return False

    def start_containers(self) -> bool:
        """
        Start the Docker containers.

        Returns:
            bool: True if containers started successfully, False otherwise
        """
        logger.info("Starting Docker containers...")

        # Determine the correct command to use
        compose_parts = self.config.docker_info.compose_command.split()
        if len(compose_parts) == 2:  # docker compose format
            cmd = [compose_parts[0], compose_parts[1], "up", "-d"]
        else:  # docker-compose format
            cmd = [compose_parts[0], "up", "-d"]

        try:
            subprocess.run(cmd, check=True)
            logger.info("Docker containers started successfully")
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to start Docker containers: {e}")
            return False

    def open_browser(self) -> None:
        """Open browser to access Magellon interfaces"""
        logger.info("Waiting for services to start up (15 seconds)...")
        time.sleep(15)

        frontend_url = f"http://localhost:{self.config.service_ports.frontend_port}/en/panel/images"
        backend_url = f"http://localhost:{self.config.service_ports.backend_port}"

        logger.info(f"Magellon is now available at:")
        logger.info(f"  - {frontend_url}")
        logger.info(f"  - {backend_url}")

        # Only try to open browser if running in a graphical environment
        if "DISPLAY" in os.environ or platform.system() == "Darwin" or platform.system() == "Windows":
            logger.info("Attempting to open browser links...")
            try:
                webbrowser.open(frontend_url)
                webbrowser.open(backend_url)
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")

    def install(self) -> bool:
        """
        Run the full installation process.

        Returns:
            bool: True if installation was successful, False otherwise
        """
        logger.info("=== Magellon Setup ===")
        logger.info(f"Setting up Magellon in: {self.config.root_dir}")

        # Run installation steps in sequence, stopping if any fail
        if not self.check_prerequisites():
            return False

        if not self.create_directory_structure():
            return False

        # Copy service files, but continue even if it fails
        self.copy_service_files()

        if not self.prepare_env_file():
            return False

        if not self.start_containers():
            return False

        # This step is optional, so we don't check its return value
        self.open_browser()

        logger.info("=== Setup process completed! ===")
        return True
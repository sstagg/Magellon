import os
import sys

import pyfiglet

from MagellonInstallationApp import MagellonInstallationApp
# Assume these modules exist in the project
from libs.models import InstallationData

import argparse
import logging

# Add the current directory to the path so we can import the libs package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from libs.config import MagellonConfig, CudaConfig
from libs.installer import MagellonInstaller
from libs.utils import setup_logging, detect_cuda_version, generate_secure_password
from libs.validator import GPUValidator


from pathlib import Path
from typing import Dict

# Global variables
installation_data = InstallationData()

class InstallationData:
    """Class to store installation configuration."""

    def __init__(self):
        # Base settings
        self.installation_type = "single"
        self.server_ip = "127.0.0.1"
        self.server_port = 8000
        self.username = ""
        self.password = ""
        self.install_dir = "/opt/magellon"

        # Installation type
        self.is_demo = True

        # Components to install
        self.install_frontend = True
        self.install_backend = True
        self.install_database = True
        self.install_queue = True

        # Database settings
        self.mysql_dbname = "magellon01"
        self.mysql_root_password = "behd1d2"
        self.mysql_user = "magellon_user"
        self.mysql_password = "behd1d2"
        self.mysql_port = 3306

        # RabbitMQ settings
        self.rabbitmq_user = "rabbit"
        self.rabbitmq_password = "behd1d2"
        self.rabbitmq_port = 5672
        self.rabbitmq_management_port = 15672

        # Grafana settings
        self.grafana_user = "admin"
        self.grafana_password = "behd1d2"
        self.grafana_port = 3000

        # Service ports
        self.consul_port = 8500
        self.frontend_port = 8080
        self.backend_port = 8000
        self.result_plugin_port = 8030
        self.ctf_plugin_port = 8035
        self.motioncor_plugin_port = 8036

        # CUDA settings
        self.cuda_version = "11.8"
        self.cuda_image = "nvidia/cuda:11.8.0-devel-ubuntu22.04"
        self.motioncor_binary = "MotionCor2_1.6.4_Cuda118_Mar312023"



def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Magellon Setup Script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "root_dir",
        help="Root directory for Magellon installation"
    )

    parser.add_argument(
        "--cuda-version",
        help="CUDA version to use (default: auto-detect)"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip GPU environment validation"
    )

    parser.add_argument(
        "--secure",
        action="store_true",
        help="Generate secure random passwords for services"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--log-dir",
        help="Directory to store log files",
        default=None
    )

    parser.add_argument(
        "--only-validate",
        action="store_true",
        help="Only run validation, don't install"
    )

    return parser.parse_args()


def validate_gpu_environment(cuda_version: str, ignore_warnings: bool = False) -> bool:
    """
    Validate the GPU environment.

    Args:
        cuda_version: Required CUDA version
        ignore_warnings: Whether to ignore warnings

    Returns:
        bool: True if validation passed, False otherwise
    """
    logger.info("Validating GPU environment...")
    validator = GPUValidator(
        required_cuda_version=cuda_version,
        quiet=False,
        ignore_warnings=ignore_warnings
    )

    if validator.validate():
        logger.info("GPU environment validation passed")
        return True
    else:
        logger.error(f"GPU environment validation failed with code: {validator.status}")
        return False


def generate_secure_configuration(config: MagellonConfig) -> Dict[str, str]:
    """
    Generate secure passwords for services.

    Args:
        config: Current Magellon configuration

    Returns:
        Dict[str, str]: Dictionary of new passwords
    """
    passwords = {}

    # Generate new passwords
    passwords["mysql_root"] = generate_secure_password(16)
    passwords["mysql_user"] = generate_secure_password(16)
    passwords["rabbitmq"] = generate_secure_password(16)
    passwords["grafana"] = generate_secure_password(16)

    # Update configuration
    config.database.root_password = passwords["mysql_root"]
    config.database.password = passwords["mysql_user"]
    config.rabbitmq.password = passwords["rabbitmq"]
    config.grafana.password = passwords["grafana"]

    return passwords


def install():
    """Main function."""
    args = parse_arguments()

    # Setup logging
    global logger
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_dir = Path(args.log_dir) if args.log_dir else None
    logger = setup_logging(log_dir, log_level)

    # Display header
    logger.info("=== Magellon Setup ===")

    # Use detected CUDA version if not specified
    cuda_version = args.cuda_version or detect_cuda_version()
    logger.info(f"Using CUDA version: {cuda_version}")

    # Validate GPU environment if requested
    if not args.skip_validation:
        if not validate_gpu_environment(cuda_version):
            if not args.only_validate:
                logger.warning("GPU validation failed but continuing with installation")

    # Exit if only validation was requested
    if args.only_validate:
        logger.info("Validation completed. Exiting as requested.")
        return

    # Create configuration
    try:
        cuda_config = CudaConfig(cuda_version=cuda_version)
        config = MagellonConfig(
            root_dir=args.root_dir,
            cuda_config=cuda_config
        )

        # Generate secure passwords if requested
        if args.secure:
            passwords = generate_secure_configuration(config)
            logger.info("Generated secure passwords:")
            for service, password in passwords.items():
                logger.info(f"  - {service}: {password}")

        # Create installer
        installer = MagellonInstaller(config)

        # Run installation
        if installer.install():
            logger.info("=== Magellon installation completed successfully! ===")

            # Print access information
            frontend_url = f"http://localhost:{config.service_ports.frontend_port}/en/panel/images"
            backend_url = f"http://localhost:{config.service_ports.backend_port}"
            logger.info(f"Magellon is available at:")
            logger.info(f"  - Frontend: {frontend_url}")
            logger.info(f"  - Backend: {backend_url}")

            sys.exit(0)
        else:
            logger.error("Installation failed")
            sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)



if __name__ == "__main__":
    # Display ASCII art header in console
    logo = pyfiglet.figlet_format('Magellon', font='speed')
    print(f"[bold blue]{logo}[/bold blue]")
    print(f"Installation Wizard v1.0")

    # Run the app
    app = MagellonInstallationApp()
    app.run()
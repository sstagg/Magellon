"""
Service management utilities for Magellon installer.

This module provides functionality for managing and configuring the
various services that make up the Magellon system.
"""

import os
import subprocess
import logging
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class ServiceManager:
    """Class to manage Magellon services"""

    def __init__(self, root_dir: Path, templates_dir: Path):
        """
        Initialize the service manager.

        Args:
            root_dir: Root directory for Magellon installation
            templates_dir: Directory containing service templates
        """
        self.root_dir = root_dir
        self.templates_dir = templates_dir
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))

    def configure_mysql(self, config: Dict[str, Any]) -> bool:
        """
        Configure MySQL service.

        Args:
            config: Configuration parameters

        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            # Create MySQL directories if they don't exist
            mysql_data_dir = self.root_dir / "services" / "mysql" / "data"
            mysql_conf_dir = self.root_dir / "services" / "mysql" / "conf"
            mysql_init_dir = self.root_dir / "services" / "mysql" / "init"

            mysql_data_dir.mkdir(parents=True, exist_ok=True)
            mysql_conf_dir.mkdir(parents=True, exist_ok=True)
            mysql_init_dir.mkdir(parents=True, exist_ok=True)

            # Copy MySQL initialization SQL if available in templates
            sql_template_path = self.templates_dir / "mysql" / "magellon01db.sql"
            if sql_template_path.exists():
                target_sql_path = mysql_init_dir / "magellon01db.sql"
                with open(sql_template_path, 'r') as src, open(target_sql_path, 'w') as dst:
                    dst.write(src.read())
                logger.info(f"Copied MySQL initialization SQL to {target_sql_path}")
            else:
                logger.warning("MySQL initialization SQL not found in templates")

            # Configure MySQL (my.cnf) if needed
            my_cnf_template = self.templates_dir / "mysql" / "my.cnf"
            if my_cnf_template.exists():
                template = self.jinja_env.get_template("mysql/my.cnf")
                my_cnf_content = template.render(**config)

                my_cnf_path = mysql_conf_dir / "my.cnf"
                with open(my_cnf_path, 'w') as f:
                    f.write(my_cnf_content)
                logger.info(f"Created MySQL configuration at {my_cnf_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to configure MySQL: {e}")
            return False

    def configure_consul(self, config: Dict[str, Any]) -> bool:
        """
        Configure Consul service.

        Args:
            config: Configuration parameters

        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            # Create Consul directories
            consul_data_dir = self.root_dir / "services" / "consul" / "data"
            consul_config_dir = self.root_dir / "services" / "consul" / "config"

            consul_data_dir.mkdir(parents=True, exist_ok=True)
            consul_config_dir.mkdir(parents=True, exist_ok=True)

            # Configure Consul if template exists
            consul_template = self.templates_dir / "consul" / "config.json"
            if consul_template.exists():
                template = self.jinja_env.get_template("consul/config.json")
                consul_config = template.render(**config)

                config_path = consul_config_dir / "config.json"
                with open(config_path, 'w') as f:
                    f.write(consul_config)
                logger.info(f"Created Consul configuration at {config_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to configure Consul: {e}")
            return False

    def configure_prometheus(self, config: Dict[str, Any]) -> bool:
        """
        Configure Prometheus service.

        Args:
            config: Configuration parameters

        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            # Create Prometheus directory
            prom_dir = self.root_dir / "services" / "prometheus"
            prom_dir.mkdir(parents=True, exist_ok=True)

            # Configure Prometheus
            template = self.jinja_env.get_template("prometheus.j2")
            prometheus_config = template.render(**config)

            config_path = prom_dir / "prometheus.yml"
            with open(config_path, 'w') as f:
                f.write(prometheus_config)
            logger.info(f"Created Prometheus configuration at {config_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to configure Prometheus: {e}")
            return False

    def configure_grafana(self, config: Dict[str, Any]) -> bool:
        """
        Configure Grafana service.

        Args:
            config: Configuration parameters

        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            # Create Grafana directory
            grafana_dir = self.root_dir / "services" / "grafana"
            grafana_dir.mkdir(parents=True, exist_ok=True)

            # Configure Grafana if needed
            # Note: In the original bash script, Grafana configuration is handled
            # through environment variables, so we may not need to create config files
            if (self.templates_dir / "grafana").exists():
                # Copy any Grafana dashboards from templates
                for dashboard_file in (self.templates_dir / "grafana" / "dashboards").glob("*.json"):
                    dashboards_dir = grafana_dir / "dashboards"
                    dashboards_dir.mkdir(exist_ok=True)
                    target_path = dashboards_dir / dashboard_file.name
                    with open(dashboard_file, 'r') as src, open(target_path, 'w') as dst:
                        dst.write(src.read())

                # Check for a grafana.db template
                db_template = self.templates_dir / "grafana" / "grafana.db"
                if db_template.exists():
                    with open(db_template, 'rb') as src, open(grafana_dir / "grafana.db", 'wb') as dst:
                        dst.write(src.read())
                    logger.info(f"Copied Grafana database to {grafana_dir / 'grafana.db'}")

            return True
        except Exception as e:
            logger.error(f"Failed to configure Grafana: {e}")
            return False

    def wait_for_service(self, service_name: str, port: int, path: str = "/", timeout: int = 60) -> bool:
        """
        Wait for a service to become available.

        Args:
            service_name: Name of the service to wait for
            port: Port the service is running on
            path: Path to check for availability
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if service becomes available, False otherwise
        """
        logger.info(f"Waiting for {service_name} to become available...")
        start_time = time.time()
        url = f"http://localhost:{port}{path}"

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code < 500:  # Accept any non-server-error response
                    logger.info(f"{service_name} is available")
                    return True
            except requests.RequestException:
                pass

            # Wait before trying again
            time.sleep(2)

        logger.warning(f"Timeout waiting for {service_name} to become available")
        return False

    def check_service_health(self, service_name: str, container_name: str) -> bool:
        """
        Check if a service is healthy.

        Args:
            service_name: Service name for logging
            container_name: Docker container name

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
                check=False, capture_output=True, text=True
            )

            status = result.stdout.strip()
            if not status:
                # No health check defined
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                    check=False, capture_output=True, text=True
                )
                status = result.stdout.strip()
                logger.info(f"{service_name} status: {status}")
                return status == "running"

            logger.info(f"{service_name} health: {status}")
            return status == "healthy"
        except Exception as e:
            logger.error(f"Failed to check {service_name} health: {e}")
            return False

    def register_service_with_consul(self, service_name: str, service_host: str,
                                     service_port: int, consul_url: str = "http://localhost:8500") -> bool:
        """
        Register a service with Consul.

        Args:
            service_name: Name of the service to register
            service_host: Host where the service is running
            service_port: Port the service is running on
            consul_url: URL for Consul API

        Returns:
            bool: True if registration was successful, False otherwise
        """
        try:
            # Service registration payload
            service_data = {
                "Name": service_name,
                "Address": service_host,
                "Port": service_port,
                "Check": {
                    "HTTP": f"http://{service_host}:{service_port}/",
                    "Interval": "10s",
                    "Timeout": "3s"
                }
            }

            # Register with Consul
            response = requests.put(
                f"{consul_url}/v1/agent/service/register",
                json=service_data
            )

            if response.status_code == 200:
                logger.info(f"Registered {service_name} with Consul")
                return True
            else:
                logger.error(f"Failed to register {service_name} with Consul: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering {service_name} with Consul: {e}")
            return False

    def configure_all_services(self, config: Dict[str, Any]) -> bool:
        """
        Configure all Magellon services.

        Args:
            config: Configuration parameters

        Returns:
            bool: True if all configurations were successful, False otherwise
        """
        # Configure each service
        success = True
        success &= self.configure_mysql({
            "database": config.get("database", "magellon01"),
            "user": config.get("user", "magellon_user"),
            "password": config.get("password", "behd1d2")
        })

        success &= self.configure_consul({
            "datacenter": "magellon",
            "bind_addr": "0.0.0.0",
            "client_addr": "0.0.0.0",
            "ui": True
        })

        success &= self.configure_prometheus({
            "scrape_interval": "15s",
            "services": [
                {"name": "prometheus", "port": 9090},
                {"name": "consul", "port": config.get("consul_port", 8500)},
                {"name": "backend", "port": config.get("backend_port", 8000)}
            ]
        })

        success &= self.configure_grafana({
            "admin_user": config.get("grafana_user", "admin"),
            "admin_password": config.get("grafana_password", "behd1d2")
        })

        return success
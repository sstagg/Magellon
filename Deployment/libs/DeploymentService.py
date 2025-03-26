import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import ansible_runner
from jinja2 import Template, Environment, FileSystemLoader

from libs.models import InstallationData


class DeploymentService:
    """Service class for handling Magellon deployment operations.

    This class separates the installation logic from the GUI,
    following a modular architecture approach.
    """

    def __init__(self, installation_data: InstallationData, base_dir: str = '.'):
        """Initialize the deployment service.

        Args:
            installation_data: Configuration data for installation
            base_dir: Base directory for file operations
        """
        self.installation_data = installation_data
        self.base_dir = Path(base_dir)
        self.templates_dir = self.base_dir / 'templates'
        self.assets_dir = self.base_dir / 'assets'
        self.output_dir = self.base_dir / 'output'

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Set up Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            variable_start_string='${',
            variable_end_string='}'
        )

    def generate_env_file(self) -> Path:
        """Generate the .env file for Docker Compose.

        Returns:
            Path to the generated .env file
        """
        template = self.jinja_env.get_template('env.j2')

        output_path = self.output_dir / '.env'

        rendered_content = template.render(
            home_path=f"{self.installation_data.core_service_server_base_directory}/home",
            gpfs_path=f"{self.installation_data.core_service_server_base_directory}/gpfs",
            jobs_path=f"{self.installation_data.core_service_server_base_directory}/jobs",
            mysql_database=self.installation_data.mysql_server_db_dbname,
            mysql_root_password=self.installation_data.mysql_server_db_password,
            mysql_user=self.installation_data.mysql_server_db_username,
            mysql_password=self.installation_data.mysql_server_db_password,
            mysql_port=self.installation_data.mysql_server_db_port_no,
            rabbitmq_user=self.installation_data.rabbitmq_username,
            rabbitmq_pass=self.installation_data.rabbitmq_password,
            rabbitmq_port=self.installation_data.rabbitmq_port,
            rabbitmq_management_port=self.installation_data.rabbitmq_management_port,
            grafana_user=self.installation_data.grafana_username,
            grafana_pass=self.installation_data.grafana_password,
            consul_port=self.installation_data.consul_port,
            frontend_port=self.installation_data.webapp_port,
            backend_port=self.installation_data.core_service_server_port,
            result_plugin_port=self.installation_data.result_plugin_port,
            ctf_plugin_port=self.installation_data.ctf_plugin_port,
            motioncor_plugin_port=self.installation_data.motioncor_plugin_port
        )

        with open(output_path, 'w') as file:
            file.write(rendered_content)

        return output_path

    def generate_docker_compose(self) -> Path:
        """Generate the docker-compose.yml file.

        Returns:
            Path to the generated docker-compose.yml file
        """
        template = self.jinja_env.get_template('docker-compose.yml.j2')

        output_path = self.output_dir / 'docker-compose.yml'

        # Determine which services to include
        services = {
            'mysql': self.installation_data.if_install_mysql,
            'rabbitmq': self.installation_data.if_install_rabbitmq,
            'consul': self.installation_data.if_install_consul,
            'prometheus': self.installation_data.if_install_prometheus,
            'grafana': self.installation_data.if_install_grafana,
            'frontend': self.installation_data.if_install_frontend,
            'backend': self.installation_data.if_install_backend,
            'result_plugin': self.installation_data.if_install_result_plugin,
            'ctf_plugin': self.installation_data.if_install_ctf_plugin,
            'motioncor_plugin': self.installation_data.if_install_motioncor_plugin
        }

        rendered_content = template.render(
            services=services,
            installation_type=self.installation_data.installation_type
        )

        with open(output_path, 'w') as file:
            file.write(rendered_content)

        return output_path

    def generate_setup_script(self) -> Path:
        """Generate the setup script for local installation.

        Returns:
            Path to the generated setup script
        """
        template = self.jinja_env.get_template('setup-script.sh.j2')

        output_path = self.output_dir / 'setup-magellon.sh'

        rendered_content = template.render(
            root_dir=self.installation_data.core_service_server_base_directory,
            server_ip=self.installation_data.core_service_server_ip,
            frontend_port=self.installation_data.webapp_port,
            backend_port=self.installation_data.core_service_server_port
        )

        with open(output_path, 'w') as file:
            file.write(rendered_content)

        # Make the script executable
        os.chmod(output_path, 0o755)

        return output_path

    def generate_ansible_files(self) -> Dict[str, Path]:
        """Generate Ansible inventory and playbook files.

        Returns:
            Dict with paths to generated inventory and playbook files
        """
        # Generate inventory file
        inventory_template = self.jinja_env.get_template('deployment_inventory.ini.j2')
        inventory_path = self.output_dir / 'inventory.ini'

        inventory_content = inventory_template.render(data=self.installation_data)
        with open(inventory_path, 'w') as file:
            file.write(inventory_content)

        # Generate playbook file
        playbook_template = self.jinja_env.get_template('deployment_playbook_template.yml.j2')
        playbook_path = self.output_dir / 'playbook.yml'

        playbook_content = playbook_template.render(data=self.installation_data)
        with open(playbook_path, 'w') as file:
            file.write(playbook_content)

        return {
            'inventory': inventory_path,
            'playbook': playbook_path
        }

    def deploy_local(self, callback_fn=None) -> Dict[str, Any]:
        """Deploy Magellon locally.

        Args:
            callback_fn: Optional callback function for progress updates

        Returns:
            Dict with deployment status and details
        """
        try:
            # Generate configuration files
            if callback_fn:
                callback_fn("Generating configuration files...", 10)

            env_path = self.generate_env_file()
            docker_compose_path = self.generate_docker_compose()
            setup_script_path = self.generate_setup_script()

            if callback_fn:
                callback_fn("Running setup script...", 30)

            # Run the setup script
            process = subprocess.Popen(
                [str(setup_script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Process output
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_line = output.strip()
                    output_lines.append(output_line)
                    if callback_fn:
                        callback_fn(output_line, None)

            return_code = process.wait()

            if return_code == 0:
                if callback_fn:
                    callback_fn("Installation completed successfully!", 100)

                return {
                    'success': True,
                    'message': "Magellon installation completed successfully!",
                    'output_lines': output_lines,
                    'frontend_url': f"http://{self.installation_data.core_service_server_ip}:{self.installation_data.webapp_port}/en/panel/images",
                    'backend_url': f"http://{self.installation_data.core_service_server_ip}:{self.installation_data.core_service_server_port}"
                }
            else:
                error_output = process.stderr.read()
                if callback_fn:
                    callback_fn(f"Installation failed: {error_output}", 100)

                return {
                    'success': False,
                    'message': "Installation failed",
                    'error': error_output,
                    'output_lines': output_lines
                }

        except Exception as e:
            if callback_fn:
                callback_fn(f"Error during installation: {str(e)}", 100)

            return {
                'success': False,
                'message': "Error during installation",
                'error': str(e)
            }

    def deploy_remote(self, callback_fn=None) -> Dict[str, Any]:
        """Deploy Magellon to a remote server using Ansible.

        Args:
            callback_fn: Optional callback function for progress updates

        Returns:
            Dict with deployment status and details
        """
        try:
            # Generate configuration files
            if callback_fn:
                callback_fn("Generating configuration files...", 10)

            env_path = self.generate_env_file()
            docker_compose_path = self.generate_docker_compose()
            setup_script_path = self.generate_setup_script()

            # Generate Ansible files
            if callback_fn:
                callback_fn("Generating Ansible files...", 20)

            ansible_files = self.generate_ansible_files()

            # Copy files to output directory if they're not already there
            for file_path in [env_path, docker_compose_path, setup_script_path]:
                dest_path = self.output_dir / file_path.name
                if file_path != dest_path:
                    shutil.copy(file_path, dest_path)

            if callback_fn:
                callback_fn("Running Ansible playbook...", 30)

            # Run Ansible playbook
            runner = ansible_runner.run(
                private_data_dir=str(self.output_dir),
                playbook=str(ansible_files['playbook'].relative_to(self.output_dir)),
                inventory=str(ansible_files['inventory'].relative_to(self.output_dir)),
                extravars={
                    'env_file_path': str(env_path.name),
                    'docker_compose_path': str(docker_compose_path.name),
                    'setup_script_path': str(setup_script_path.name),
                    'base_dir': self.installation_data.core_service_server_base_directory
                },
                quiet=False
            )

            # Process output
            if runner.status == 'successful':
                if callback_fn:
                    callback_fn("Installation completed successfully!", 100)

                return {
                    'success': True,
                    'message': "Magellon installation completed successfully!",
                    'frontend_url': f"http://{self.installation_data.core_service_server_ip}:{self.installation_data.webapp_port}/en/panel/images",
                    'backend_url': f"http://{self.installation_data.core_service_server_ip}:{self.installation_data.core_service_server_port}"
                }
            else:
                if callback_fn:
                    callback_fn(f"Installation failed: {runner.stderr}", 100)

                return {
                    'success': False,
                    'message': "Installation failed",
                    'error': runner.stderr
                }

        except Exception as e:
            if callback_fn:
                callback_fn(f"Error during installation: {str(e)}", 100)

            return {
                'success': False,
                'message': "Error during installation",
                'error': str(e)
            }

    def deploy(self, callback_fn=None) -> Dict[str, Any]:
        """Deploy Magellon based on installation configuration.
        
        This method determines whether to use local or remote deployment
        based on the installation data.

        Args:
            callback_fn: Optional callback function for progress updates

        Returns:
            Dict with deployment status and details
        """
        if self.installation_data.core_service_server_ip in ['localhost', '127.0.0.1']:
            return self.deploy_local(callback_fn)
        else:
            return self.deploy_remote(callback_fn)
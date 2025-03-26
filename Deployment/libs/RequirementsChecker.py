import os
import subprocess
import shutil
import socket
import paramiko
from typing import Dict, List, Any, Tuple, Optional


class RequirementsChecker:
    """Class for checking system requirements for Magellon installation."""

    def __init__(self, host: str = 'localhost', username: Optional[str] = None, password: Optional[str] = None):
        """Initialize the requirements checker.

        Args:
            host: Target host to check requirements on
            username: SSH username for remote host
            password: SSH password for remote host
        """
        self.host = host
        self.username = username
        self.password = password
        self.is_remote = host not in ['localhost', '127.0.0.1']
        self.ssh_client = None

        if self.is_remote and self.username and self.password:
            self._setup_ssh_connection()

    def _setup_ssh_connection(self) -> None:
        """Set up SSH connection to remote host."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                timeout=10
            )
        except Exception as e:
            print(f"Error setting up SSH connection: {e}")
            self.ssh_client = None

    def _execute_command(self, command: str) -> Tuple[str, str, int]:
        """Execute a command on the target host.

        Args:
            command: Command to execute

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        if self.is_remote and self.ssh_client:
            # Execute on remote host
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            return (
                stdout.read().decode('utf-8'),
                stderr.read().decode('utf-8'),
                stdout.channel.recv_exit_status()
            )
        else:
            # Execute locally
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            return stdout, stderr, process.returncode

    def check_docker(self) -> Dict[str, Any]:
        """Check if Docker is installed and get its version.

        Returns:
            Dict with 'installed' (bool) and 'version' (str) if installed
        """
        stdout, stderr, return_code = self._execute_command("docker --version")

        if return_code == 0:
            # Docker is installed, extract version
            version = stdout.strip()
            return {
                'installed': True,
                'version': version
            }
        else:
            return {
                'installed': False,
                'error': stderr.strip()
            }

    def check_docker_compose(self) -> Dict[str, Any]:
        """Check if Docker Compose is installed and get its version.

        Returns:
            Dict with 'installed' (bool) and 'version' (str) if installed
        """
        # Try docker-compose v1 first
        stdout, stderr, return_code = self._execute_command("docker-compose --version")

        if return_code == 0:
            # Docker Compose v1 is installed
            version = stdout.strip()
            return {
                'installed': True,
                'version': version,
                'variant': 'v1'
            }

        # Try docker compose v2
        stdout, stderr, return_code = self._execute_command("docker compose version")

        if return_code == 0:
            # Docker Compose v2 is installed
            version = stdout.strip()
            return {
                'installed': True,
                'version': version,
                'variant': 'v2'
            }

        return {
            'installed': False,
            'error': stderr.strip()
        }

    def check_git(self) -> Dict[str, Any]:
        """Check if Git is installed and get its version.

        Returns:
            Dict with 'installed' (bool) and 'version' (str) if installed
        """
        stdout, stderr, return_code = self._execute_command("git --version")

        if return_code == 0:
            # Git is installed, extract version
            version = stdout.strip()
            return {
                'installed': True,
                'version': version
            }
        else:
            return {
                'installed': False,
                'error': stderr.strip()
            }

    def check_disk_space(self, directory: str = '/opt/magellon') -> Dict[str, Any]:
        """Check if there's enough disk space for installation.

        Args:
            directory: Target installation directory

        Returns:
            Dict with 'sufficient' (bool), 'available' (float) in GB, and 'required' (float) in GB
        """
        required_gb = 5.0  # Require at least 5GB of free space

        if self.is_remote and self.ssh_client:
            # Check disk space on remote host
            stdout, stderr, return_code = self._execute_command(f"df -BG --output=avail {os.path.dirname(directory)} | tail -n 1")

            if return_code == 0:
                available_gb = float(stdout.strip().replace('G', ''))
                return {
                    'sufficient': available_gb >= required_gb,
                    'available': available_gb,
                    'required': required_gb
                }
        else:
            # Check disk space locally
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(directory), exist_ok=True)

                # Get disk usage statistics
                usage = shutil.disk_usage(os.path.dirname(directory))
                available_gb = usage.free / (1024 ** 3)  # Convert to GB

                return {
                    'sufficient': available_gb >= required_gb,
                    'available': round(available_gb, 2),
                    'required': required_gb
                }
            except Exception as e:
                return {
                    'sufficient': False,
                    'error': str(e),
                    'required': required_gb
                }

        return {
            'sufficient': False,
            'error': 'Failed to check disk space',
            'required': required_gb
        }

    def check_ports(self, ports: List[int]) -> List[Dict[str, Any]]:
        """Check if required ports are available.

        Args:
            ports: List of port numbers to check

        Returns:
            List of dicts with 'port' (int), 'available' (bool), and 'process' (str) if not available
        """
        results = []

        for port in ports:
            if self.is_remote and self.ssh_client:
                # Check port on remote host
                stdout, stderr, return_code = self._execute_command(f"ss -tuln | grep :{port}")

                if stdout.strip():
                    # Port is in use
                    process_stdout, _, _ = self._execute_command(f"lsof -i :{port} | tail -n 1")
                    process = process_stdout.strip().split()[0] if process_stdout.strip() else "Unknown"

                    results.append({
                        'port': port,
                        'available': False,
                        'process': process
                    })
                else:
                    # Port is available
                    results.append({
                        'port': port,
                        'available': True
                    })
            else:
                # Check port locally
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)

                try:
                    sock.connect(('localhost', port))
                    # Port is in use
                    sock.close()

                    # Try to identify the process
                    try:
                        process_stdout, _, _ = self._execute_command(f"lsof -i :{port} | tail -n 1")
                        process = process_stdout.strip().split()[0] if process_stdout.strip() else "Unknown"
                    except:
                        process = "Unknown"

                    results.append({
                        'port': port,
                        'available': False,
                        'process': process
                    })
                except:
                    # Port is available
                    results.append({
                        'port': port,
                        'available': True
                    })

        return results

    def check_all(self) -> Dict[str, Any]:
        """Run all requirement checks and return a combined result.

        Returns:
            Dict containing all check results
        """
        docker_result = self.check_docker()
        docker_compose_result = self.check_docker_compose()
        git_result = self.check_git()
        disk_space_result = self.check_disk_space()

        # Check essential ports
        ports_to_check = [8000, 8080, 3306, 5672, 15672, 8500, 8030, 8035, 8036]
        ports_result = self.check_ports(ports_to_check)

        # Determine if all requirements are met
        all_requirements_met = (
                docker_result.get('installed', False) and
                docker_compose_result.get('installed', False) and
                disk_space_result.get('sufficient', False) and
                all(result.get('available', False) for result in ports_result)
        )

        return {
            'all_requirements_met': all_requirements_met,
            'docker': docker_result,
            'docker_compose': docker_compose_result,
            'git': git_result,
            'disk_space': disk_space_result,
            'ports': ports_result
        }

    def __del__(self):
        """Clean up SSH connection when object is destroyed."""
        if self.ssh_client:
            self.ssh_client.close()
"""
Screen for checking system requirements.
"""

import os
import shutil
import subprocess
from typing import Dict, List, Tuple

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, ProgressBar, TextLog, Footer
from textual.containers import Container, Horizontal

from header import MagellonHeader

class RequirementsScreen(Screen):
    """Screen for checking system requirements."""

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="requirements-container"):
            yield Static("System Requirements Check", id="screen-title")

            yield ProgressBar(id="check-progress", total=100)
            yield TextLog(id="check-log", markup=True)

            with Horizontal(id="action-buttons"):
                yield Button("Close", id="close-button", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        """When screen is mounted, start the checks."""
        self.run_checks()

    def run_checks(self) -> None:
        """Run system requirement checks."""
        progress_bar = self.query_one("#check-progress", ProgressBar)
        log = self.query_one("#check-log", TextLog)

        # Check Docker installation
        log.write("[bold blue]Checking Docker installation...[/bold blue]")
        progress_bar.update(progress=10)

        docker_installed, docker_output = self.check_docker()
        if docker_installed:
            log.write(f"[green]✓ Docker installed: {docker_output}[/green]")
        else:
            log.write(f"[red]✗ Docker not installed or not running: {docker_output}[/red]")
            log.write("[yellow]Docker is required for Magellon installation.[/yellow]")

        # Check Docker Compose
        log.write("[bold blue]Checking Docker Compose...[/bold blue]")
        progress_bar.update(progress=30)

        compose_installed, compose_cmd, compose_output = self.check_docker_compose()
        if compose_installed:
            log.write(f"[green]✓ Docker Compose installed: {compose_output}[/green]")
            log.write(f"[green]Using command: {compose_cmd}[/green]")
        else:
            log.write(f"[red]✗ Docker Compose not found: {compose_output}[/red]")
            log.write("[yellow]Docker Compose is required for Magellon installation.[/yellow]")

        # Check GPU capabilities
        log.write("[bold blue]Checking GPU capabilities...[/bold blue]")
        progress_bar.update(progress=50)

        gpu_available, gpu_output = self.check_nvidia_docker()
        if gpu_available:
            log.write(f"[green]✓ GPU support available: {gpu_output}[/green]")
        else:
            log.write(f"[yellow]⚠ GPU support not detected: {gpu_output}[/yellow]")
            log.write("[yellow]GPU support is recommended but not required.[/yellow]")

        # Check disk space
        log.write("[bold blue]Checking disk space...[/bold blue]")
        progress_bar.update(progress=70)

        disk_space_sufficient, disk_space_gb = self.check_disk_space(self.app.installation_data.install_dir)
        if disk_space_sufficient:
            log.write(f"[green]✓ Sufficient disk space: {disk_space_gb:.1f} GB available[/green]")
        else:
            log.write(f"[red]✗ Insufficient disk space: only {disk_space_gb:.1f} GB available[/red]")
            log.write("[yellow]At least 10 GB of free disk space is recommended.[/yellow]")

        # Check port availability
        log.write("[bold blue]Checking port availability...[/bold blue]")
        progress_bar.update(progress=90)

        ports_to_check = [
            self.app.installation_data.frontend_port,
            self.app.installation_data.backend_port,
            self.app.installation_data.mysql_port,
            self.app.installation_data.rabbitmq_port,
            self.app.installation_data.rabbitmq_management_port,
            self.app.installation_data.consul_port,
            self.app.installation_data.result_plugin_port,
            self.app.installation_data.ctf_plugin_port,
            self.app.installation_data.motioncor_plugin_port
        ]

        used_ports = self.check_ports(ports_to_check)
        if not used_ports:
            log.write("[green]✓ All required ports are available[/green]")
        else:
            log.write("[yellow]⚠ Some required ports are already in use:[/yellow]")
            for port, process in used_ports.items():
                log.write(f"[red]  - Port {port} is in use by {process}[/red]")
            log.write("[yellow]You will need to choose different ports or stop these services.[/yellow]")

        # Complete check
        progress_bar.update(progress=100)

        # Overall status
        all_required = docker_installed and compose_installed and disk_space_sufficient
        if all_required and not used_ports:
            log.write("[bold green]✓ All requirements are met! Ready to install Magellon.[/bold green]")
        elif all_required:
            log.write("[bold yellow]⚠ Core requirements are met, but some ports are in use.[/bold yellow]")
        else:
            log.write("[bold red]✗ Some core requirements are not met. Please resolve issues before continuing.[/bold red]")

    def check_docker(self) -> Tuple[bool, str]:
        """Check if Docker is installed and running."""
        try:
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

    def check_docker_compose(self) -> Tuple[bool, str, str]:
        """Check which version of Docker Compose is available."""
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

    def check_nvidia_docker(self) -> Tuple[bool, str]:
        """Check if NVIDIA Container Toolkit is installed and configured."""
        # Skip check if docker is not available
        docker_available, docker_msg = self.check_docker()
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

    def check_disk_space(self, directory: str) -> Tuple[bool, float]:
        """Check available disk space in GB."""
        try:
            if not os.path.exists(directory):
                # Check parent directory or create the path
                os.makedirs(directory, exist_ok=True)

            # Get disk usage statistics
            stat = shutil.disk_usage(directory)
            free_gb = stat.free / (1024 * 1024 * 1024)  # Convert bytes to GB

            # Require at least 10 GB of free space
            return free_gb >= 10, free_gb
        except Exception as e:
            return False, 0.0

    def check_ports(self, ports: List[int]) -> Dict[int, str]:
        """Check if ports are already in use. Returns dict of used ports and processes."""
        used_ports = {}

        for port in ports:
            try:
                # Using netstat to check if port is in use
                result = subprocess.run(
                    ["netstat", "-tuln"],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Parse output to find ports in use
                if f":{port}" in result.stdout:
                    # Try to get the process using this port
                    try:
                        pid_result = subprocess.run(
                            ["lsof", "-i", f":{port}"],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        # Extract process name
                        lines = pid_result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            process = lines[1].split()[0]
                            used_ports[port] = process
                        else:
                            used_ports[port] = "unknown process"
                    except Exception:
                        used_ports[port] = "unknown process"
            except Exception:
                # If netstat fails, assume port is free
                continue

        return used_ports

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "close-button":
            self.app.pop_screen()
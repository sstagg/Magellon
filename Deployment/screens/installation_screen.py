"""
Screen showing installation progress.
"""

import os
import sys
import subprocess
import time
import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, ProgressBar, TextLog, Button, Footer

from header import MagellonHeader
from libs.config import MagellonConfig, CudaConfig, DockerInfo

class InstallationScreen(Screen):
    """Screen showing installation progress."""

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def __init__(self, phase: int = 1):
        """
        Initialize the installation screen.

        Args:
            phase: Installation phase (1 = prepare, 2 = run containers)
        """
        super().__init__()
        self.phase = phase

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="installation-container"):
            yield Static("Installation Progress", id="screen-title")

            # Progress indicator
            with Horizontal(id="progress-steps"):
                yield Static("1", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("2", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("3", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("4", classes="step active")

            yield ProgressBar(total=100, show_eta=True, id="installation-progress")
            yield TextLog(id="installation-log", highlight=True, markup=True)

            with Horizontal(id="action-buttons"):
                yield Button("Cancel", id="cancel-button", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        """When the screen is mounted, start the installation."""
        # Start installation in a worker task
        self.run_installation()

    def run_installation(self) -> None:
        """Run the actual installation process."""
        progress_bar = self.query_one("#installation-progress", ProgressBar)
        log = self.query_one("#installation-log", TextLog)

        # Create MagellonConfig from our installation data
        data = self.app.installation_data

        try:
            # Create configuration
            log.write("[bold blue]Preparing installation...[/bold blue]")
            progress_bar.update(progress=5)

            log.write("Creating configuration...")
            cuda_config = CudaConfig(cuda_version=data.cuda_version)
            config = MagellonConfig(
                root_dir=data.install_dir,
                cuda_config=cuda_config
            )

            # Update configuration with user settings
            config.database.database = data.mysql_dbname
            config.database.root_password = data.mysql_root_password
            config.database.user = data.mysql_user
            config.database.password = data.mysql_password
            config.database.port = data.mysql_port

            config.rabbitmq.user = data.rabbitmq_user
            config.rabbitmq.password = data.rabbitmq_password
            config.rabbitmq.port = data.rabbitmq_port
            config.rabbitmq.management_port = data.rabbitmq_management_port

            config.grafana.user = data.grafana_user
            config.grafana.password = data.grafana_password

            config.service_ports.frontend_port = data.frontend_port
            config.service_ports.backend_port = data.backend_port
            config.service_ports.consul_port = data.consul_port
            config.service_ports.result_plugin_port = data.result_plugin_port
            config.service_ports.ctf_plugin_port = data.ctf_plugin_port
            config.service_ports.motioncor_plugin_port = data.motioncor_plugin_port

            log.write("[green]✓ Configuration created successfully[/green]")
            progress_bar.update(progress=10)

            # Phase 1: Preparation
            if self.phase == 1:
                # Create directory structure
                log.write("[bold blue]Creating directory structure...[/bold blue]")
                progress_bar.update(progress=20)

                root_dir = Path(data.install_dir)
                self.create_directories(root_dir, config.required_directories, log)
                progress_bar.update(progress=40)

                # Prepare .env file
                log.write("[bold blue]Preparing environment variables...[/bold blue]")
                progress_bar.update(progress=60)

                env_vars = config.get_env_variables()
                env_file = self.create_env_file(env_vars, log)
                progress_bar.update(progress=80)

                # Copy service files if available
                log.write("[bold blue]Checking for service files...[/bold blue]")
                progress_bar.update(progress=90)

                services_dir = Path.cwd() / "services"
                self.copy_services(services_dir, root_dir, log)

                # Phase 1 complete
                progress_bar.update(progress=100)
                log.write("[bold green]✓ Phase 1 completed successfully![/bold green]")
                log.write("[green]Directories created and .env file generated[/green]")
                log.write("[blue]You can now proceed to Phase 2 to start the containers[/blue]")

                # Change cancel button to next phase
                cancel_button = self.query_one("#cancel-button", Button)
                cancel_button.label = "Start Phase 2"
                cancel_button.variant = "success"
                cancel_button.id = "next-phase-button"

            # Phase 2: Start containers
            elif self.phase == 2:
                # Determine Docker Compose command
                log.write("[bold blue]Determining Docker Compose command...[/bold blue]")
                progress_bar.update(progress=20)

                docker_compose_cmd = self.get_docker_compose_command(log)
                progress_bar.update(progress=40)

                # Start containers
                log.write("[bold blue]Starting Docker containers...[/bold blue]")
                progress_bar.update(progress=60)

                success = self.start_containers(docker_compose_cmd, log)

                if success:
                    progress_bar.update(progress=80)
                    log.write("[green]✓ Docker containers started successfully[/green]")

                    # Wait for services to start
                    log.write("[bold blue]Waiting for services to start (this may take a minute)...[/bold blue]")
                    time.sleep(15)  # Give services some time to start

                    # Complete installation
                    progress_bar.update(progress=100)
                    frontend_url = f"http://localhost:{data.frontend_port}/en/panel/images"
                    backend_url = f"http://localhost:{data.backend_port}"

                    log.write("[bold green]✓ Phase 2 completed successfully![/bold green]")
                    log.write("[blue]Magellon is now available at:[/blue]")
                    log.write(f"[blue]  - Frontend: {frontend_url}[/blue]")
                    log.write(f"[blue]  - Backend: {backend_url}[/blue]")

                    # Change cancel button to finish
                    cancel_button = self.query_one("#cancel-button", Button)
                    cancel_button.label = "Finish"
                    cancel_button.variant = "success"
                else:
                    progress_bar.update(progress=100)
                    log.write("[bold red]✗ Container startup failed![/bold red]")
                    log.write("[yellow]Please check the logs for more information.[/yellow]")

        except Exception as e:
            progress_bar.update(progress=100)
            log.write(f"[bold red]✗ Installation failed with error: {str(e)}[/bold red]")

    def create_directories(self, root_dir: Path, directories: list, log: TextLog) -> None:
        """Create the required directory structure."""
        try:
            # Create the root directory if it doesn't exist
            os.makedirs(root_dir, exist_ok=True)
            log.write(f"[green]✓ Created root directory: {root_dir}[/green]")

            # Create all required directories
            for dir_path in directories:
                full_path = root_dir / dir_path
                os.makedirs(full_path, exist_ok=True)
                log.write(f"[green]✓ Created directory: {full_path}[/green]")

            # Set permissions (similar to chmod 777 in bash script)
            if sys.platform != "win32":
                for dir_path in directories:
                    full_path = root_dir / dir_path
                    try:
                        # This is equivalent to chmod 777 in the bash script
                        os.chmod(full_path, 0o777)
                    except Exception as e:
                        log.write(f"[yellow]⚠ Failed to set permissions on {full_path}: {e}[/yellow]")

            log.write("[green]✓ Directory structure created successfully[/green]")
        except Exception as e:
            log.write(f"[red]✗ Failed to create directory structure: {e}[/red]")
            raise

    def create_env_file(self, env_vars: dict, log: TextLog) -> Path:
        """Create the .env file with environment variables."""
        try:
            env_file = Path.cwd() / ".env"

            # Write environment variables to .env file
            with open(env_file, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")

            # Create a backup
            env_backup = Path.cwd() / ".env.backup"
            shutil.copy2(env_file, env_backup)

            log.write(f"[green]✓ Created .env file: {env_file}[/green]")
            log.write(f"[green]✓ Created backup: {env_backup}[/green]")

            return env_file
        except Exception as e:
            log.write(f"[red]✗ Failed to create .env file: {e}[/red]")
            raise

    def copy_services(self, services_dir: Path, root_dir: Path, log: TextLog) -> None:
        """Copy service files if they exist in the current directory."""
        if not services_dir.exists():
            log.write("[yellow]⚠ 'services' directory not found in current location[/yellow]")
            return

        log.write("Copying services directory...")
        dest_services_dir = root_dir / "services"

        try:
            if sys.platform == "win32":
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

            log.write("[green]✓ Services directory copied successfully[/green]")
        except Exception as e:
            log.write(f"[yellow]⚠ Failed to copy services directory: {e}[/yellow]")

    def get_docker_compose_command(self, log: TextLog) -> str:
        """Determine which Docker Compose command to use."""
        # First try Docker Compose V2 (plugin)
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                check=True,
                capture_output=True,
                text=True
            )
            log.write("[green]✓ Using Docker Compose V2 (plugin)[/green]")
            return "docker compose"
        except subprocess.SubprocessError:
            # Try Docker Compose V1 (standalone)
            try:
                subprocess.run(
                    ["docker-compose", "--version"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                log.write("[green]✓ Using Docker Compose V1 (standalone)[/green]")
                return "docker-compose"
            except subprocess.SubprocessError:
                log.write("[red]✗ Neither docker compose nor docker-compose found[/red]")
                raise RuntimeError("Docker Compose not found")

    def start_containers(self, compose_command: str, log: TextLog) -> bool:
        """Start Docker containers using Docker Compose."""
        try:
            # Split the command into parts
            cmd_parts = compose_command.split() + ["up", "-d"]

            # Run the command
            log.write(f"Running command: {' '.join(cmd_parts)}")
            process = subprocess.run(
                cmd_parts,
                check=True,
                capture_output=True,
                text=True
            )

            # Check if the command was successful
            if process.returncode == 0:
                return True
            else:
                log.write(f"[red]✗ Docker Compose command failed with code {process.returncode}[/red]")
                log.write(f"[red]Error: {process.stderr}[/red]")
                return False
        except subprocess.SubprocessError as e:
            log.write(f"[red]✗ Failed to start Docker containers: {e}[/red]")
            return False
        except Exception as e:
            log.write(f"[red]✗ Unexpected error: {e}[/red]")
            return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "cancel-button":
            # Get button label to determine if installation is complete
            button = self.query_one("#cancel-button", Button)

            if button.label == "Finish":
                # Installation complete, return to main screen
                self.app.switch_screen("welcome_screen")
            else:
                # Ask for confirmation to cancel installation
                self.app.push_screen("quit_screen", self.app.check_quit)

        elif button_id == "next-phase-button":
            # Start phase 2 of the installation
            self.app.pop_screen()
            self.app.push_screen(InstallationScreen(phase=2))
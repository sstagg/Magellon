from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label, ProgressBar
from textual.containers import Vertical, Horizontal

from libs.RequirementsChecker import RequirementsChecker


class RequirementsScreen(Screen):
    """Screen for displaying system requirements check results."""

    def __init__(self, host='localhost', username=None, password=None, install_dir='/opt/magellon', ports=None):
        super().__init__()
        self.host = host
        self.username = username
        self.password = password
        self.install_dir = install_dir
        self.ports = ports or [8000, 8080, 3306, 5672, 15672, 8500, 8030, 8035, 8036]
        self.checker = RequirementsChecker(host, username, password)
        self.results = None

    def compose(self) -> ComposeResult:
        yield Static("Checking System Requirements for Magellon", id="requirements-title")

        with Vertical(id="requirements-container"):
            yield Label("Please wait while we check your system...", id="checking-label")
            yield ProgressBar(total=100, id="check-progress")

            with Vertical(id="results-container"):
                yield Static("", id="docker-check")
                yield Static("", id="compose-check")
                yield Static("", id="git-check")
                yield Static("", id="disk-check")
                yield Static("", id="ports-check")
                yield Static("", id="summary")

        with Horizontal(id="button-container"):
            yield Button("Save Report", id="save-report-btn", variant="primary")
            yield Button("Close", id="close-btn", variant="error")

    async def on_mount(self) -> None:
        """Run the checks when the screen is mounted."""
        self.run_checks()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.dismiss(False)  # Close the screen
        elif event.button.id == "save-report-btn":
            self.save_report()

    def run_checks(self) -> None:
        """Run all system requirement checks."""
        progress = self.query_one("#check-progress", ProgressBar)

        # Start checking
        self.update_progress(progress, 10, "Checking Docker installation...")
        docker_result = self.checker.check_docker()

        self.update_progress(progress, 30, "Checking Docker Compose installation...")
        compose_result = self.checker.check_docker_compose()

        self.update_progress(progress, 50, "Checking Git installation...")
        git_result = self.checker.check_git()

        self.update_progress(progress, 70, "Checking available disk space...")
        disk_result = self.checker.check_disk_space(self.install_dir)

        self.update_progress(progress, 90, "Checking port availability...")
        ports_result = self.checker.check_ports(self.ports)

        # Store all results
        self.results = {
            'docker': docker_result,
            'docker_compose': compose_result,
            'git': git_result,
            'disk_space': disk_result,
            'ports': ports_result
        }

        # Complete
        self.update_progress(progress, 100, "Checks completed!")

        # Update UI with results
        self.show_check_results()

    def update_progress(self, progress_bar: ProgressBar, value: int, message: str) -> None:
        """Update progress bar and checking label."""
        progress_bar.update(progress=value)
        self.query_one("#checking-label", Label).update(message)

    def show_check_results(self) -> None:
        """Display check results in the UI."""
        # Docker check
        docker_widget = self.query_one("#docker-check", Static)
        if self.results['docker'].get('installed', False):
            docker_widget.update(f"✅ [green]Docker:[/green] {self.results['docker']['version']}")
        else:
            docker_widget.update(f"❌ [red]Docker:[/red] Not installed. {self.results['docker'].get('error', '')}")
            docker_widget.update(docker_widget.render() + "\n[yellow]Docker is required to run Magellon.[/yellow]")

        # Docker Compose check
        compose_widget = self.query_one("#compose-check", Static)
        if self.results['docker_compose'].get('installed', False):
            compose_widget.update(f"✅ [green]Docker Compose:[/green] {self.results['docker_compose']['version']} ({self.results['docker_compose'].get('variant', 'unknown variant')})")
        else:
            compose_widget.update(f"❌ [red]Docker Compose:[/red] Not installed. {self.results['docker_compose'].get('error', '')}")
            compose_widget.update(compose_widget.render() + "\n[yellow]Docker Compose is required to run Magellon.[/yellow]")

        # Git check
        git_widget = self.query_one("#git-check", Static)
        if self.results['git'].get('installed', False):
            git_widget.update(f"✅ [green]Git:[/green] {self.results['git']['version']}")
        else:
            git_widget.update(f"⚠️ [yellow]Git:[/yellow] Not installed. {self.results['git'].get('error', '')}")
            git_widget.update(git_widget.render() + "\n[yellow]Git is recommended but not required.[/yellow]")

        # Disk space check
        disk_widget = self.query_one("#disk-check", Static)
        if self.results['disk_space'].get('sufficient', False):
            disk_widget.update(f"✅ [green]Disk Space:[/green] {self.results['disk_space']['available']} GB available (minimum required: {self.results['disk_space']['required']} GB)")
        else:
            disk_widget.update(f"❌ [red]Disk Space:[/red] Only {self.results['disk_space'].get('available', 0)} GB available (minimum required: {self.results['disk_space']['required']} GB)")
            if 'error' in self.results['disk_space']:
                disk_widget.update(disk_widget.render() + f"\n[red]Error: {self.results['disk_space']['error']}[/red]")
            disk_widget.update(disk_widget.render() + "\n[yellow]Magellon requires at least 5GB of free disk space.[/yellow]")

        # Ports check
        ports_widget = self.query_one("#ports-check", Static)
        used_ports = [p for p in self.results['ports'] if not p.get('available', False)]

        if not used_ports:
            ports_widget.update("✅ [green]Ports:[/green] All required ports are available")
        else:
            ports_widget.update("⚠️ [yellow]Ports:[/yellow] Some required ports are already in use:")
            for port_info in used_ports:
                ports_widget.update(ports_widget.render() + f"\n[red]  - Port {port_info.get('port', '?')} is used by {port_info.get('process', 'unknown process')}[/red]")
            ports_widget.update(ports_widget.render() + "\n[yellow]You may need to modify port assignments or stop services using these ports.[/yellow]")

        # Summary
        summary_widget = self.query_one("#summary", Static)

        # Check if all essential requirements are met
        essential_met = (
                self.results['docker'].get('installed', False) and
                self.results['docker_compose'].get('installed', False) and
                self.results['disk_space'].get('sufficient', False)
        )

        if essential_met and not used_ports:
            summary_widget.update("[bold green]✅ All requirements are met! Magellon can be installed successfully.[/bold green]")
        elif essential_met and used_ports:
            summary_widget.update("[bold yellow]⚠️ Essential requirements are met, but")
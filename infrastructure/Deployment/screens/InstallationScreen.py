from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, ProgressBar, TextLog, Button, Footer

from screens.MagellonHeader import MagellonHeader
from screens.quit_screen import QuitScreen


class InstallationScreen(Screen):
    """Screen showing installation progress."""

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
    ]

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
        # In a real app, this would be a worker task
        self.simulate_installation()

    def simulate_installation(self) -> None:
        """Simulate the installation process."""
        progress_bar = self.query_one("#installation-progress", ProgressBar)
        log = self.query_one("#installation-log", TextLog)

        # Log initial message
        log.write("[bold blue]Starting Magellon installation...[/bold blue]")
        progress_bar.update(progress=5)

        # Simulate checking requirements
        log.write("Checking system requirements...")
        progress_bar.update(progress=10)
        log.write("[green]✓ System meets minimum requirements[/green]")

        # Simulate creating directories
        log.write("Creating installation directories...")
        progress_bar.update(progress=15)
        log.write(f"[green]✓ Created directory: {self.app.installation_data.install_dir}[/green]")

        # Simulate installing components based on configuration
        if self.app.installation_data.installation_type == "single":
            # Simulate database installation
            if getattr(self.app.installation_data, "install_database", True):
                log.write("Installing MySQL database...")
                progress_bar.update(progress=30)
                log.write("[green]✓ MySQL database installed successfully[/green]")

            # Simulate message queue installation
            if getattr(self.app.installation_data, "install_queue", True):
                log.write("Installing RabbitMQ message queue...")
                progress_bar.update(progress=45)
                log.write("[green]✓ RabbitMQ installed successfully[/green]")

            # Simulate backend installation
            if getattr(self.app.installation_data, "install_backend", True):
                log.write("Installing backend services...")
                progress_bar.update(progress=60)
                log.write("[green]✓ Backend services installed successfully[/green]")

            # Simulate frontend installation
            if getattr(self.app.installation_data, "install_frontend", True):
                log.write("Installing frontend UI...")
                progress_bar.update(progress=75)
                log.write("[green]✓ Frontend UI installed successfully[/green]")

        # Network installation specific components
        elif self.app.installation_data.installation_type == "network":
            log.write("Setting up master node...")
            progress_bar.update(progress=30)
            log.write("[green]✓ Master node configured successfully[/green]")

            log.write("Configuring worker nodes...")
            progress_bar.update(progress=50)
            log.write("[green]✓ Worker nodes configured successfully[/green]")

            log.write("Setting up distributed services...")
            progress_bar.update(progress=70)
            log.write("[green]✓ Distributed services configured successfully[/green]")

        # Cloud installation specific components
        elif self.app.installation_data.installation_type == "cloud":
            log.write("Provisioning cloud resources...")
            progress_bar.update(progress=30)
            log.write("[green]✓ Cloud resources provisioned successfully[/green]")

            log.write("Deploying containers...")
            progress_bar.update(progress=50)
            log.write("[green]✓ Containers deployed successfully[/green]")

            log.write("Configuring cloud services...")
            progress_bar.update(progress=70)
            log.write("[green]✓ Cloud services configured successfully[/green]")

        # Simulate configuration
        log.write("Configuring Magellon services...")
        progress_bar.update(progress=85)
        log.write("[green]✓ Services configured successfully[/green]")

        # Simulate starting services
        log.write("Starting Magellon services...")
        progress_bar.update(progress=95)
        log.write("[green]✓ All services started successfully[/green]")

        # Complete installation
        progress_bar.update(progress=100)
        log.write("[bold green]✓ Installation completed successfully![/bold green]")
        log.write("[blue]Magellon is now ready to use.[/blue]")

        # Change cancel button to finish
        cancel_button = self.query_one("#cancel-button", Button)
        cancel_button.label = "Finish"
        cancel_button.variant = "success"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "cancel-button":
            # If installation is complete (progress is 100%), exit app
            progress_bar = self.query_one("#installation-progress", ProgressBar)
            if progress_bar.progress == 100:
                self.app.exit()
            else:
                # Otherwise, confirm cancellation
                self.app.push_screen(QuitScreen(), self.app.check_quit)

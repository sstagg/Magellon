"""
Confirmation screen before installation.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, Button, Footer

from header import MagellonHeader
from screens.installation_screen import InstallationScreen

class ConfirmationScreen(Screen):
    """Confirmation screen before installation."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="confirmation-container"):
            yield Static("Installation Confirmation", id="screen-title")

            # Progress indicator
            with Horizontal(id="progress-steps"):
                yield Static("1", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("2", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("3", classes="step active")
                yield Static("→", classes="step-arrow")
                yield Static("4", classes="step")

            yield Static("Please review your installation configuration:", classes="section-title")

            with Container(id="configuration-summary"):
                yield Static(f"Installation Type: Single Computer", classes="config-item")
                yield Static(f"Installation Directory: {str(self.app.installation_data.install_dir)}", classes="config-item")

                yield Static("CUDA Configuration:", classes="subsection-title")
                yield Static(f"CUDA Version: {self.app.installation_data.cuda_version}", classes="config-item")
                yield Static(f"CUDA Image: {self.app.installation_data.cuda_image}", classes="config-item")
                yield Static(f"MotionCor Binary: {self.app.installation_data.motioncor_binary}", classes="config-item")
                yield Static(f"Installation Mode: {'Demo' if self.app.installation_data.is_demo else 'Production'}", classes="config-item")

                yield Static("Components:", classes="subsection-title")
                yield Static(f"Frontend UI: {'Yes' if self.app.installation_data.install_frontend else 'No'}", classes="config-item")
                yield Static(f"Backend Services: {'Yes' if self.app.installation_data.install_backend else 'No'}", classes="config-item")
                yield Static(f"Database (MySQL): {'Yes' if self.app.installation_data.install_database else 'No'}", classes="config-item")
                yield Static(f"Message Queue (RabbitMQ): {'Yes' if self.app.installation_data.install_queue else 'No'}", classes="config-item")

                yield Static("Port Configuration:", classes="subsection-title")
                yield Static(f"Frontend Port: {self.app.installation_data.frontend_port}", classes="config-item")
                yield Static(f"Backend Port: {self.app.installation_data.backend_port}", classes="config-item")
                yield Static(f"MySQL Port: {self.app.installation_data.mysql_port}", classes="config-item")
                yield Static(f"RabbitMQ Port: {self.app.installation_data.rabbitmq_port}", classes="config-item")

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="default")
                yield Button("Phase 1: Prepare", id="phase1-button", variant="primary")
                yield Button("Phase 2: Start", id="phase2-button", variant="success")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()
        elif button_id == "phase1-button":
            self.app.push_screen(InstallationScreen(phase=1))
        elif button_id == "phase2-button":
            self.app.push_screen(InstallationScreen(phase=2))

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()
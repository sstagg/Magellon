from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, Button, Footer

from screens.MagellonHeader import MagellonHeader
from screens.InstallationScreen import InstallationScreen


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
                # This would be populated dynamically based on the selected options
                yield Static(f"Installation Type: {self.app.installation_data.installation_type.title()}", classes="config-item")

                # Render different configuration details based on installation type
                if self.app.installation_data.installation_type == "single":
                    yield Static("Single Computer Configuration:", classes="subsection-title")
                    yield Static(f"Server IP: {self.app.installation_data.server_ip}", classes="config-item")
                    yield Static(f"Port: {self.app.installation_data.server_port}", classes="config-item")
                    yield Static(f"Username: {self.app.installation_data.username}", classes="config-item")
                    yield Static(f"Installation Directory: {self.app.installation_data.install_dir}", classes="config-item")
                    yield Static(f"Installation Mode: {'Demo' if self.app.installation_data.is_demo else 'Production'}", classes="config-item")

                    yield Static("Components:", classes="subsection-title")
                    yield Static(f"Frontend UI: {'Yes' if self.app.installation_data.install_frontend else 'No'}", classes="config-item")
                    yield Static(f"Backend Services: {'Yes' if self.app.installation_data.install_backend else 'No'}", classes="config-item")
                    yield Static(f"Database (MySQL): {'Yes' if self.app.installation_data.install_database else 'No'}", classes="config-item")
                    yield Static(f"Message Queue (RabbitMQ): {'Yes' if self.app.installation_data.install_queue else 'No'}", classes="config-item")

                elif self.app.installation_data.installation_type == "network":
                    yield Static("Network configuration details would be displayed here", classes="config-item")

                elif self.app.installation_data.installation_type == "cloud":
                    yield Static("Cloud configuration details would be displayed here", classes="config-item")

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="default")
                yield Button("Install", id="install-button", variant="success")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()

        elif button_id == "install-button":
            self.app.push_screen(InstallationScreen())

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

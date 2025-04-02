from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.validation import Regex
from textual.widgets import Static, TabbedContent, TabPane, Input, Button, Switch, Footer

from screens.MagellonHeader import MagellonHeader
from screens.confirmation_screen import ConfirmationScreen


class NetworkScreen(Screen):
    """Configuration screen for network deployment."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="config-container"):
            yield Static("Network Deployment", id="screen-title")

            # Progress indicator
            with Horizontal(id="progress-steps"):
                yield Static("1", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("2", classes="step active")
                yield Static("→", classes="step-arrow")
                yield Static("3", classes="step")
                yield Static("→", classes="step-arrow")
                yield Static("4", classes="step")

            with TabbedContent(id="config-tabs"):
                with TabPane("Master Node", id="master-tab"):
                    yield Static("Master Node Configuration", classes="section-title")

                    yield Static("Master IP Address:", classes="input-label")
                    yield Input(
                        placeholder="Enter IP address",
                        id="master_ip",
                        validators=[Regex(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")],
                    )
                    yield Static("", id="master-ip-error", classes="validation-error")

                    yield Static("Admin Username:", classes="input-label")
                    yield Input(
                        placeholder="Enter admin username",
                        id="admin_username"
                    )

                    yield Static("Admin Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter admin password",
                        id="admin_password",
                        password=True
                    )

                    yield Static("Base Directory:", classes="input-label")
                    yield Input(
                        placeholder="Enter installation directory",
                        id="master_install_dir",
                        value="/opt/magellon"
                    )

                with TabPane("Worker Nodes", id="workers-tab"):
                    yield Static("Worker Nodes Configuration", classes="section-title")

                    yield Static("Worker nodes list will be displayed here", id="workers-list")

                    yield Button("Add Worker Node", id="add-worker", variant="success")

                with TabPane("Components", id="components-tab"):
                    yield Static("Components Configuration", classes="section-title")

                    with Grid(id="network-components-grid"):
                        with Horizontal(classes="component-row"):
                            yield Static("Frontend UI", classes="component-name")
                            yield Switch(value=True, id="net_frontend_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Backend Services", classes="component-name")
                            yield Switch(value=True, id="net_backend_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Database Cluster", classes="component-name")
                            yield Switch(value=True, id="net_database_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Message Queue Cluster", classes="component-name")
                            yield Switch(value=True, id="net_queue_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Load Balancer", classes="component-name")
                            yield Switch(value=True, id="load_balancer_switch")

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="default")
                yield Button("Check Network", id="check-network", variant="primary")
                yield Button("Next", id="next-button", variant="success")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()

        elif button_id == "check-network":
            # This would check network connectivity in a real implementation
            self.app.notify("Network check functionality not implemented in this demo")

        elif button_id == "next-button":
            # In a real app, validate and save configuration
            self.app.push_screen(ConfirmationScreen())

        elif button_id == "add-worker":
            # This would open a dialog to add a worker node in a real implementation
            self.app.notify("Add worker node functionality not implemented in this demo")

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

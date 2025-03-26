from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.validation import Regex, Number
from textual.widgets import Static, TabbedContent, TabPane, Input, Button, Switch, Footer

from screens.MagellonHeader import MagellonHeader
from screens.ConfirmationScreen import ConfirmationScreen


class SingleComputerScreen(Screen):
    """Configuration screen for single computer installation."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="config-container"):
            yield Static("Single Computer Installation", id="screen-title")

            # Progress indicator
            with Horizontal(id="progress-steps"):
                yield Static("1", classes="step completed")
                yield Static("→", classes="step-arrow")
                yield Static("2", classes="step active")
                yield Static("→", classes="step-arrow")
                yield Static("3", classes="step")
                yield Static("→", classes="step-arrow")
                yield Static("4", classes="step")

            # Configuration form
            with TabbedContent(id="config-tabs"):
                with TabPane("Connection", id="connection-tab"):
                    yield Static("Connection Settings", classes="section-title")

                    yield Static("Server IP Address:", classes="input-label")
                    ip_input = Input(
                        placeholder="Enter IP address (e.g., 127.0.0.1)",
                        id="server_ip",
                        value="127.0.0.1",
                        validators=[Regex(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")],
                    )
                    yield ip_input
                    yield Static("", id="ip-error", classes="validation-error")

                    yield Static("Port Number:", classes="input-label")
                    port_input = Input(
                        placeholder="Enter port number (1024-65535)",
                        id="server_port",
                        value="8000",
                        validators=[Number(minimum=1024, maximum=65535)],
                    )
                    yield port_input
                    yield Static("", id="port-error", classes="validation-error")

                    yield Static("Username:", classes="input-label")
                    yield Input(
                        placeholder="Enter username",
                        id="username"
                    )

                    yield Static("Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter password",
                        id="password",
                        password=True
                    )

                with TabPane("Installation", id="installation-tab"):
                    yield Static("Installation Settings", classes="section-title")

                    yield Static("Base Directory:", classes="input-label")
                    yield Input(
                        placeholder="Enter installation directory",
                        id="install_dir",
                        value="/opt/magellon"
                    )

                    yield Static("Installation Type:", classes="input-label")
                    with Horizontal(id="install-type-options"):
                        yield Button("Demo", id="demo-option", variant="primary")
                        yield Button("Production", id="production-option", variant="default")

                    yield Static("Components:", classes="section-title")

                    with Grid(id="components-grid"):
                        with Horizontal(classes="component-row"):
                            yield Static("Frontend UI", classes="component-name")
                            yield Switch(value=True, id="frontend_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Backend Services", classes="component-name")
                            yield Switch(value=True, id="backend_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Database (MySQL)", classes="component-name")
                            yield Switch(value=True, id="database_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Message Queue (RabbitMQ)", classes="component-name")
                            yield Switch(value=True, id="queue_switch")

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="default")
                yield Button("Check Requirements", id="check-button", variant="primary")
                yield Button("Next", id="next-button", variant="success")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()

        elif button_id == "check-button":
            self.app.action_check_requirements()

        elif button_id == "next-button":
            # Validate inputs
            valid = True

            # Check IP input
            ip_input = self.query_one("#server_ip", Input)
            if not ip_input.is_valid:
                self.query_one("#ip-error").update("Please enter a valid IP address")
                valid = False
            else:
                self.query_one("#ip-error").update("")

            # Check port input
            port_input = self.query_one("#server_port", Input)
            if not port_input.is_valid:
                self.query_one("#port-error").update("Please enter a valid port number (1024-65535)")
                valid = False
            else:
                self.query_one("#port-error").update("")

            # If validation passes, save data and proceed
            if valid:
                # Save data to installation_data
                self.app.installation_data.server_ip = ip_input.value
                self.app.installation_data.server_port = int(port_input.value)
                self.app.installation_data.username = self.query_one("#username").value
                self.app.installation_data.password = self.query_one("#password").value
                self.app.installation_data.install_dir = self.query_one("#install_dir").value

                # Get installation type
                self.app.installation_data.is_demo = self.query_one("#demo-option").variant == "primary"

                # Get component selections
                self.app.installation_data.install_frontend = self.query_one("#frontend_switch").value
                self.app.installation_data.install_backend = self.query_one("#backend_switch").value
                self.app.installation_data.install_database = self.query_one("#database_switch").value
                self.app.installation_data.install_queue = self.query_one("#queue_switch").value

                # Proceed to confirmation screen
                self.app.push_screen(ConfirmationScreen())

        elif button_id == "demo-option":
            self.query_one("#demo-option").variant = "primary"
            self.query_one("#production-option").variant = "default"

        elif button_id == "production-option":
            self.query_one("#demo-option").variant = "default"
            self.query_one("#production-option").variant = "primary"

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

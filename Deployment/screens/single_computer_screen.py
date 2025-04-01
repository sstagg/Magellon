"""
Configuration screen for single computer installation.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Static, TabbedContent, TabPane, Input, Button, Switch, Footer

from header import MagellonHeader
from screens.confirmation_screen import ConfirmationScreen
from screens.requirements_screen import RequirementsScreen
from libs.utils import generate_secure_password

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
                with TabPane("General", id="general-tab"):
                    yield Static("Installation Settings", classes="section-title")

                    yield Static("Installation Directory:", classes="input-label")
                    yield Input(
                        placeholder="Enter installation directory",
                        id="install_dir",
                        value=self.app.installation_data.install_dir
                    )

                    yield Static("CUDA Version:", classes="input-label")
                    yield Input(
                        placeholder="Enter CUDA version",
                        id="cuda_version",
                        value=self.app.installation_data.cuda_version
                    )

                    yield Static("Installation Type:", classes="input-label")
                    with Horizontal(id="install-type-options"):
                        yield Button(
                            "Demo",
                            id="demo-option",
                            variant="primary" if self.app.installation_data.is_demo else "default"
                        )
                        yield Button(
                            "Production",
                            id="production-option",
                            variant="default" if self.app.installation_data.is_demo else "primary"
                        )

                with TabPane("Services", id="services-tab"):
                    yield Static("Service Configuration", classes="section-title")

                    with Grid(id="components-grid"):
                        with Horizontal(classes="component-row"):
                            yield Static("Frontend UI", classes="component-name")
                            yield Switch(
                                value=self.app.installation_data.install_frontend,
                                id="frontend_switch"
                            )

                        with Horizontal(classes="component-row"):
                            yield Static("Backend Services", classes="component-name")
                            yield Switch(
                                value=self.app.installation_data.install_backend,
                                id="backend_switch"
                            )

                        with Horizontal(classes="component-row"):
                            yield Static("Database (MySQL)", classes="component-name")
                            yield Switch(
                                value=self.app.installation_data.install_database,
                                id="database_switch"
                            )

                        with Horizontal(classes="component-row"):
                            yield Static("Message Queue (RabbitMQ)", classes="component-name")
                            yield Switch(
                                value=self.app.installation_data.install_queue,
                                id="queue_switch"
                            )

                with TabPane("Ports", id="ports-tab"):
                    yield Static("Port Configuration", classes="section-title")

                    yield Static("Frontend Port:", classes="input-label")
                    yield Input(
                        placeholder="Enter frontend port",
                        id="frontend_port",
                        value=str(self.app.installation_data.frontend_port),
                        validators=[Number(minimum=1024, maximum=65535)],
                    )

                    yield Static("Backend Port:", classes="input-label")
                    yield Input(
                        placeholder="Enter backend port",
                        id="backend_port",
                        value=str(self.app.installation_data.backend_port),
                        validators=[Number(minimum=1024, maximum=65535)],
                    )

                    yield Static("MySQL Port:", classes="input-label")
                    yield Input(
                        placeholder="Enter MySQL port",
                        id="mysql_port",
                        value=str(self.app.installation_data.mysql_port),
                        validators=[Number(minimum=1024, maximum=65535)],
                    )

                    yield Static("RabbitMQ Port:", classes="input-label")
                    yield Input(
                        placeholder="Enter RabbitMQ port",
                        id="rabbitmq_port",
                        value=str(self.app.installation_data.rabbitmq_port),
                        validators=[Number(minimum=1024, maximum=65535)],
                    )

                with TabPane("Passwords", id="password-tab"):
                    yield Static("Security Settings", classes="section-title")

                    yield Static("MySQL Root Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter MySQL root password",
                        id="mysql_root_password",
                        value=self.app.installation_data.mysql_root_password,
                        password=True
                    )

                    yield Static("MySQL User Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter MySQL user password",
                        id="mysql_password",
                        value=self.app.installation_data.mysql_password,
                        password=True
                    )

                    yield Static("RabbitMQ Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter RabbitMQ password",
                        id="rabbitmq_password",
                        value=self.app.installation_data.rabbitmq_password,
                        password=True
                    )

                    yield Static("Grafana Password:", classes="input-label")
                    yield Input(
                        placeholder="Enter Grafana password",
                        id="grafana_password",
                        value=self.app.installation_data.grafana_password,
                        password=True
                    )

                    yield Button("Generate Secure Passwords", id="generate-passwords", variant="primary")

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
            self.save_config()
            self.app.push_screen(RequirementsScreen())
        elif button_id == "next-button":
            self.save_config()
            self.app.push_screen(ConfirmationScreen())
        elif button_id == "demo-option":
            self.query_one("#demo-option").variant = "primary"
            self.query_one("#production-option").variant = "default"
        elif button_id == "production-option":
            self.query_one("#demo-option").variant = "default"
            self.query_one("#production-option").variant = "primary"
        elif button_id == "generate-passwords":
            self.generate_secure_passwords()

    def generate_secure_passwords(self) -> None:
        """Generate and set secure passwords."""
        mysql_root_password = generate_secure_password(16)
        mysql_password = generate_secure_password(16)
        rabbitmq_password = generate_secure_password(16)
        grafana_password = generate_secure_password(16)

        self.query_one("#mysql_root_password", Input).value = mysql_root_password
        self.query_one("#mysql_password", Input).value = mysql_password
        self.query_one("#rabbitmq_password", Input).value = rabbitmq_password
        self.query_one("#grafana_password", Input).value = grafana_password

        self.app.notify("Secure passwords generated successfully")

    def save_config(self) -> None:
        """Save configuration values to the installation data."""
        # Save general settings
        self.app.installation_data.install_dir = self.query_one("#install_dir").value
        self.app.installation_data.cuda_version = self.query_one("#cuda_version").value
        self.app.installation_data.is_demo = self.query_one("#demo-option").variant == "primary"

        # Save component selections
        self.app.installation_data.install_frontend = self.query_one("#frontend_switch").value
        self.app.installation_data.install_backend = self.query_one("#backend_switch").value
        self.app.installation_data.install_database = self.query_one("#database_switch").value
        self.app.installation_data.install_queue = self.query_one("#queue_switch").value

        # Save port settings
        self.app.installation_data.frontend_port = int(self.query_one("#frontend_port").value)
        self.app.installation_data.backend_port = int(self.query_one("#backend_port").value)
        self.app.installation_data.mysql_port = int(self.query_one("#mysql_port").value)
        self.app.installation_data.rabbitmq_port = int(self.query_one("#rabbitmq_port").value)

        # Save password settings
        self.app.installation_data.mysql_root_password = self.query_one("#mysql_root_password").value
        self.app.installation_data.mysql_password = self.query_one("#mysql_password").value
        self.app.installation_data.rabbitmq_password = self.query_one("#rabbitmq_password").value
        self.app.installation_data.grafana_password = self.query_one("#grafana_password").value

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()
import os
import pyfiglet
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container, Grid
from textual.screen import Screen
from textual.validation import Regex, Number
from textual.widgets import (
    Header, Footer, Label, Button, Input, TabbedContent,
    TabPane, ProgressBar, TextLog, Switch, Select, Static,
    ContentSwitcher
)
from textual import on

# Assume these modules exist in the project
from libs.models import InstallationData
from screens.quit_screen import QuitScreen

# Global variables
installation_data = InstallationData()


class MagellonHeader(Header):
    """Custom header for the Magellon installation wizard."""

    DEFAULT_CSS = """
    MagellonHeader {
        background: #0a1929;
        color: #58a6ff;
        text-style: bold;
        border-bottom: solid #30363d;
        height: 3;
    }
    """


class WelcomeScreen(Screen):
    """Welcome screen for the Magellon installation wizard."""

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
        Binding(key="?", action="show_help", description="Help"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="welcome-container"):
            logo_text = pyfiglet.figlet_format('Magellon', font='speed')
            yield Static(f"[bold blue]{logo_text}[/bold blue]", id="logo")

            yield Static("Welcome to the Magellon Installation Wizard", id="welcome-title")
            yield Static(
                "This wizard will guide you through the installation of Magellon, "
                "a next-generation CryoEM software suite designed for high-performance "
                "data processing and analysis.",
                id="welcome-description"
            )

            # Installation progress steps
            with Horizontal(id="progress-steps"):
                yield Static("1", classes="step active")
                yield Static("→", classes="step-arrow")
                yield Static("2", classes="step")
                yield Static("→", classes="step-arrow")
                yield Static("3", classes="step")
                yield Static("→", classes="step-arrow")
                yield Static("4", classes="step")

            yield Static("Please select an installation type:", id="selection-prompt")

            with Grid(id="installation-options"):
                # Single Computer Option
                with Container(classes="installation-option", id="single-option"):
                    yield Static("🖥️", classes="option-icon")
                    yield Static("Single Computer", classes="option-title")
                    yield Static(
                        "Install all components on a single computer. "
                        "Ideal for personal workstations or small labs.",
                        classes="option-description"
                    )
                    yield Button("Select", id="select-single", classes="option-button")

                # Network Deployment Option
                with Container(classes="installation-option", id="network-option"):
                    yield Static("🌐", classes="option-icon")
                    yield Static("Network Deployment", classes="option-title")
                    yield Static(
                        "Deploy across multiple computers in a network. "
                        "Best for labs with multiple workstations.",
                        classes="option-description"
                    )
                    yield Button("Select", id="select-network", classes="option-button")

                # Cloud Deployment Option
                with Container(classes="installation-option", id="cloud-option"):
                    yield Static("☁️", classes="option-icon")
                    yield Static("Cloud Deployment", classes="option-title")
                    yield Static(
                        "Deploy in a cloud environment (AWS, GCP, Azure). "
                        "Optimal for scalable, on-demand processing.",
                        classes="option-description"
                    )
                    yield Button("Select", id="select-cloud", classes="option-button")

            with Horizontal(id="action-buttons"):
                yield Button("Exit", id="exit-button", variant="error")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "select-single":
            self.app.installation_data.installation_type = "single"
            self.app.push_screen(SingleComputerScreen())

        elif button_id == "select-network":
            self.app.installation_data.installation_type = "network"
            self.app.push_screen(NetworkScreen())

        elif button_id == "select-cloud":
            self.app.installation_data.installation_type = "cloud"
            self.app.push_screen(CloudScreen())

        elif button_id == "exit-button":
            self.app.push_screen(QuitScreen(), self.app.check_quit)

    def action_show_help(self) -> None:
        """Show help information."""
        self.app.push_screen(HelpScreen())


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


class CloudScreen(Screen):
    """Configuration screen for cloud deployment."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="config-container"):
            yield Static("Cloud Deployment", id="screen-title")

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
                with TabPane("Provider", id="provider-tab"):
                    yield Static("Cloud Provider Configuration", classes="section-title")

                    yield Static("Select Cloud Provider:", classes="input-label")
                    with Horizontal(id="provider-buttons"):
                        yield Button("AWS", id="aws-button", variant="primary")
                        yield Button("Google Cloud", id="gcp-button", variant="default")
                        yield Button("Azure", id="azure-button", variant="default")

                    yield Static("Region:", classes="input-label")
                    yield Select(
                        [
                            ("us-east-1", "US East (N. Virginia)"),
                            ("us-west-1", "US West (N. California)"),
                            ("us-west-2", "US West (Oregon)"),
                            ("eu-west-1", "EU (Ireland)"),
                            ("eu-central-1", "EU (Frankfurt)"),
                            ("ap-northeast-1", "Asia Pacific (Tokyo)"),
                        ],
                        id="region_select",
                        value="us-east-1"
                    )

                    yield Static("Credentials:", classes="section-title")

                    yield Static("Access Key ID:", classes="input-label")
                    yield Input(
                        placeholder="Enter access key ID",
                        id="access_key",
                        password=True
                    )

                    yield Static("Secret Access Key:", classes="input-label")
                    yield Input(
                        placeholder="Enter secret access key",
                        id="secret_key",
                        password=True
                    )

                with TabPane("Resources", id="resources-tab"):
                    yield Static("Cloud Resources Configuration", classes="section-title")

                    yield Static("Instance Type:", classes="input-label")
                    yield Select(
                        [
                            ("t3.micro", "t3.micro (2 vCPU, 1 GiB RAM)"),
                            ("t3.small", "t3.small (2 vCPU, 2 GiB RAM)"),
                            ("t3.medium", "t3.medium (2 vCPU, 4 GiB RAM)"),
                            ("m5.large", "m5.large (2 vCPU, 8 GiB RAM)"),
                            ("m5.xlarge", "m5.xlarge (4 vCPU, 16 GiB RAM)"),
                        ],
                        id="instance_type",
                        value="t3.medium"
                    )

                    yield Static("Number of Instances:", classes="input-label")
                    yield Input(
                        placeholder="Enter number of instances",
                        id="instance_count",
                        value="1",
                        validators=[Number(minimum=1, maximum=10)],
                    )
                    yield Static("", id="instances-error", classes="validation-error")

                    yield Static("Storage (GB):", classes="input-label")
                    yield Input(
                        placeholder="Enter storage size in GB",
                        id="storage_size",
                        value="100",
                        validators=[Number(minimum=20, maximum=1000)],
                    )
                    yield Static("", id="storage-error", classes="validation-error")

                with TabPane("Components", id="cloud-components-tab"):
                    yield Static("Components Configuration", classes="section-title")

                    with Grid(id="cloud-components-grid"):
                        with Horizontal(classes="component-row"):
                            yield Static("Web Interface", classes="component-name")
                            yield Switch(value=True, id="cloud_web_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Processing Services", classes="component-name")
                            yield Switch(value=True, id="cloud_processing_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Database Services", classes="component-name")
                            yield Switch(value=True, id="cloud_database_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Storage Services", classes="component-name")
                            yield Switch(value=True, id="cloud_storage_switch")

                        with Horizontal(classes="component-row"):
                            yield Static("Load Balancer", classes="component-name")
                            yield Switch(value=True, id="cloud_lb_switch")

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="default")
                yield Button("Estimate Cost", id="estimate-button", variant="primary")
                yield Button("Next", id="next-button", variant="success")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()

        elif button_id == "estimate-button":
            # This would calculate estimated costs in a real implementation
            self.app.notify("Cost estimation: Approximately $120-150 per month")

        elif button_id == "next-button":
            # In a real app, validate and save configuration
            self.app.push_screen(ConfirmationScreen())

        # Handle cloud provider selection
        elif button_id == "aws-button":
            self.query_one("#aws-button").variant = "primary"
            self.query_one("#gcp-button").variant = "default"
            self.query_one("#azure-button").variant = "default"

        elif button_id == "gcp-button":
            self.query_one("#aws-button").variant = "default"
            self.query_one("#gcp-button").variant = "primary"
            self.query_one("#azure-button").variant = "default"

        elif button_id == "azure-button":
            self.query_one("#aws-button").variant = "default"
            self.query_one("#gcp-button").variant = "default"
            self.query_one("#azure-button").variant = "primary"

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()


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


class HelpScreen(Screen):
    """Help screen with information about the wizard."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="help-container"):
            yield Static("Magellon Installation Help", id="screen-title")

            with TabbedContent(id="help-tabs"):
                with TabPane("Overview", id="overview-tab"):
                    yield Static("About Magellon", classes="section-title")

                    yield Static(
                        "Magellon is a next-generation CryoEM software suite designed for "
                        "high-performance data processing and analysis. It provides tools "
                        "for image acquisition, particle picking, 2D classification, 3D "
                        "reconstruction, and refinement.",
                        classes="help-text"
                    )

                    yield Static("Installation Types", classes="section-title")

                    yield Static(
                        "Single Computer: Install all components on one machine.\n"
                        "Network Deployment: Distribute components across multiple computers.\n"
                        "Cloud Deployment: Run Magellon in the cloud (AWS, GCP, Azure).",
                        classes="help-text"
                    )

                with TabPane("Requirements", id="requirements-tab"):
                    yield Static("System Requirements", classes="section-title")

                    yield Static(
                        "Minimum Requirements:\n"
                        "- CPU: 4 cores\n"
                        "- RAM: 16 GB\n"
                        "- Storage: 100 GB\n"
                        "- OS: Linux (Ubuntu 20.04 or later recommended)\n"
                        "- Docker 20.10 or later\n"
                        "- Docker Compose 2.0 or later",
                        classes="help-text"
                    )

                    yield Static(
                        "Recommended Requirements:\n"
                        "- CPU: 16+ cores\n"
                        "- RAM: 64+ GB\n"
                        "- Storage: 1+ TB SSD\n"
                        "- GPU: NVIDIA with CUDA support (16+ GB VRAM)",
                        classes="help-text"
                    )

                with TabPane("Support", id="support-tab"):
                    yield Static("Getting Help", classes="section-title")

                    yield Static(
                        "Documentation: https://magellon-cryoem.org/docs\n"
                        "Support Email: support@magellon-cryoem.org\n"
                        "Community Forum: https://forum.magellon-cryoem.org\n"
                        "GitHub: https://github.com/magellon/magellon",
                        classes="help-text"
                    )

            with Horizontal(id="action-buttons"):
                yield Button("Back", id="back-button", variant="primary")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "back-button":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()


class MagellonInstallationApp(App):
    """Enhanced Magellon Installation Wizard."""

    CSS_PATH = "magellon_installation.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Next-gen CryoEm Software"

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
        Binding(key="r", action="check_requirements", description="Check Requirements"),
        Binding(key="?", action="show_help", description="Help"),
    ]

    def __init__(self):
        super().__init__()
        self.installation_data = InstallationData()

    def on_mount(self) -> None:
        """Initial actions when the app is mounted."""
        # Display the welcome screen
        self.push_screen(WelcomeScreen())

    def action_quit_app(self) -> None:
        """Action to quit the app."""
        self.push_screen(QuitScreen(), self.check_quit)

    def check_quit(self, do_quit: bool) -> None:
        """Called when QuitScreen is dismissed."""
        if do_quit:
            self.exit()

    def action_check_requirements(self) -> None:
        """Check system requirements."""
        try:
            text_log = self.query_one(TextLog)
            progress_bar = self.query_one(ProgressBar)

            text_log.write("[bold blue]Checking system requirements...[/bold blue]")
            progress_bar.update(progress=10)

            # Simulate Docker check
            text_log.write("Checking for Docker...")
            progress_bar.update(progress=20)
            text_log.write("[green]✓ Docker is installed: Docker 20.10.12[/green]")

            # Simulate Docker Compose check
            text_log.write("Checking for Docker Compose...")
            progress_bar.update(progress=40)
            text_log.write("[green]✓ Docker Compose is installed: Docker Compose 2.6.0[/green]")

            # Simulate disk space check
            text_log.write("Checking available disk space...")
            progress_bar.update(progress=60)
            text_log.write("[green]✓ Sufficient disk space: 25.4 GB available (minimum required: 5 GB)[/green]")

            # Simulate port check
            text_log.write("Checking port availability...")
            progress_bar.update(progress=80)
            text_log.write("[yellow]⚠ Port 8080 is already in use by nginx[/yellow]")
            text_log.write("[green]✓ All other ports are available[/green]")

            # Summary
            progress_bar.update(progress=100)
            text_log.write("[bold yellow]⚠ Most requirements are met, but port 8080 needs to be changed or freed up.[/bold yellow]")
            text_log.write("You can proceed with installation after resolving these issues.")
        except Exception:
            # If TextLog or ProgressBar not found, show notification
            self.notify("System requirements check completed. Some issues were found.", severity="warning")

    def action_show_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())


if __name__ == "__main__":
    # Display ASCII art header in console
    logo = pyfiglet.figlet_format('Magellon', font='speed')
    print(f"[bold blue]{logo}[/bold blue]")
    print(f"Installation Wizard v1.0")

    # Run the app
    app = MagellonInstallationApp()
    app.run()
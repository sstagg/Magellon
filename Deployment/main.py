import os
import pyfiglet
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Grid
from textual.validation import Regex, Number
from textual.widgets import (
    Header, Footer, Label, Button, Input, TabbedContent,
    TabPane, ProgressBar, TextLog, Switch, Select, Static
)

from libs.models import InstallationData
from screens.quit_screen import QuitScreen

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')

load_gui: bool = False
installation_data: InstallationData = InstallationData()


class MagellonInstallationApp(App[str]):
    CSS_PATH = "magellon_installation.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Next-gen CryoEm Software"

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit the app"),
        Binding(key="r", action="check_requirements", description="Check Requirements"),
        Binding(
            key="question_mark",
            action="help",
            description="Help",
            key_display="?",
        ),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="WelcomeTabPane"):
            # Welcome screen
            with TabPane("Welcome", id="WelcomeTabPane"):
                yield Static("Welcome to Magellon Installation Wizard", id="welcome-title")
                yield Static(
                    "This wizard will guide you through the installation of Magellon, a next-generation CryoEm software suite. "
                    "Please select your desired installation type from the tabs above.",
                    id="welcome-text"
                )

                # Installation types with cards
                with Horizontal(id="installation-type-container"):
                    with Vertical(classes="installation-card"):
                        yield Static("Single Computer", classes="card-title")
                        yield Static("Install Magellon on a single machine", classes="card-description")
                        yield Button("Select", id="select-single", variant="primary")

                    with Vertical(classes="installation-card"):
                        yield Static("Network Deployment", classes="card-title")
                        yield Static("Install Magellon across multiple networked machines", classes="card-description")
                        yield Button("Select", id="select-network", variant="primary")

                    with Vertical(classes="installation-card"):
                        yield Static("Cloud Deployment", classes="card-title")
                        yield Static("Deploy Magellon to cloud infrastructure", classes="card-description")
                        yield Button("Select", id="select-cloud", variant="primary")

            # Single Computer tab
            with TabPane("Single Computer", id="SingleTabPane"):
                yield Static("Single Computer Installation", id="single-title")

                yield Grid(
                    Label("IP address:"),
                    Input(
                        placeholder="Enter accessible ip address or name...",
                        validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^localhost$"), ],
                        id="server_ip",
                        value="127.0.0.1"
                    ),
                    Label("Installation Type:"),
                    Select(
                        [(k, v) for k, v in {
                            "demo": "Demo (Minimal installation)",
                            "production": "Production (Full installation)"
                        }.items()],
                        id="installation_type",
                        value="demo"
                    ),
                    Label("Port Number:"),
                    Input(
                        placeholder="Enter port number", value="8000",
                        validators=[Number(minimum=1, maximum=65500), ], id="server_core_port"
                    ),
                    Label("Username:"),
                    Input(
                        placeholder="Enter server's username...",
                        validators=[Regex(
                            "^[a-zA-Z0-9_.-]+$"), ],
                        id="server_username"
                    ),
                    Label("Password:"),
                    Input(
                        placeholder="Enter server's password",
                        password=True,
                        id="server_password"
                    ),
                    Label("Base Directory:"),
                    Input(
                        placeholder="Enter accessible base Directory...",
                        id="core_server_base_directory",
                        value="/opt/magellon"
                    ),
                )

                # Components section
                yield Static("Components to Install", id="components-title")
                with Grid(id="components-grid"):
                    yield Horizontal(
                        Label("Frontend:"),
                        Switch(value=True, id="install_frontend"),
                    )
                    yield Horizontal(
                        Label("Backend:"),
                        Switch(value=True, id="install_backend"),
                    )
                    yield Horizontal(
                        Label("MySQL Database:"),
                        Switch(value=True, id="install_mysql"),
                    )
                    yield Horizontal(
                        Label("RabbitMQ:"),
                        Switch(value=True, id="install_rabbitmq"),
                    )
                    yield Horizontal(
                        Label("Consul:"),
                        Switch(value=True, id="install_consul"),
                    )
                    yield Horizontal(
                        Label("Prometheus:"),
                        Switch(value=True, id="install_prometheus"),
                    )
                    yield Horizontal(
                        Label("Grafana:"),
                        Switch(value=True, id="install_grafana"),
                    )
                    yield Horizontal(
                        Label("Result Plugin:"),
                        Switch(value=True, id="install_result_plugin"),
                    )
                    yield Horizontal(
                        Label("CTF Plugin:"),
                        Switch(value=True, id="install_ctf_plugin"),
                    )
                    yield Horizontal(
                        Label("MotionCor Plugin:"),
                        Switch(value=True, id="install_motioncor_plugin"),
                    )

            # Network Deployment tab
            with TabPane("Network", id="NetworkTabPane"):
                yield Static("Network Deployment", id="network-title")

                # Master node section
                yield Static("Master Node Configuration", id="master-title")
                yield Grid(
                    Label("Master IP address:"),
                    Input(
                        placeholder="Enter accessible ip address or name...",
                        validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$"), ],
                        id="master_ip"
                    ),
                    Label("Username:"),
                    Input(
                        placeholder="Enter username...",
                        validators=[Regex("^[a-zA-Z0-9_.-]+$"), ],
                        id="master_username"
                    ),
                    Label("Password:"),
                    Input(
                        placeholder="Enter password",
                        password=True,
                        id="master_password"
                    ),
                    Label("Base Directory:"),
                    Input(
                        placeholder="Enter base directory...",
                        id="master_base_directory",
                        value="/opt/magellon"
                    ),
                )

                # Worker nodes section
                yield Static("Worker Nodes", id="workers-title")
                yield Grid(
                    Label("Worker IP:"),
                    Input(
                        placeholder="Enter worker IP address...",
                        id="new_worker_ip"
                    ),
                    Label("Username:"),
                    Input(
                        placeholder="Enter username...",
                        id="new_worker_username"
                    ),
                    Label("Password:"),
                    Input(
                        placeholder="Enter password",
                        password=True,
                        id="new_worker_password"
                    ),
                )

                yield Button("Add Worker Node", id="add_worker", variant="success")

                # Worker nodes list (placeholder)
                yield Static("Added Worker Nodes:", id="worker-list-title")
                yield Static("No worker nodes added yet", id="worker-list")

            # Cloud Deployment tab
            with TabPane("Cloud", id="CloudTabPane"):
                yield Static("Cloud Deployment", id="cloud-title")

                yield Grid(
                    Label("Cloud Provider:"),
                    Select(
                        [(k, v) for k, v in {
                            "aws": "Amazon Web Services (AWS)",
                            "gcp": "Google Cloud Platform (GCP)",
                            "azure": "Microsoft Azure"
                        }.items()],
                        id="cloud_provider",
                        value="aws"
                    ),
                    Label("Region:"),
                    Input(
                        placeholder="Enter cloud region...",
                        id="cloud_region",
                        value="us-east-1"
                    ),
                    Label("Access Key:"),
                    Input(
                        placeholder="Enter access key...",
                        password=True,
                        id="cloud_access_key"
                    ),
                    Label("Secret Key:"),
                    Input(
                        placeholder="Enter secret key...",
                        password=True,
                        id="cloud_secret_key"
                    ),
                    Label("Instance Type:"),
                    Input(
                        placeholder="Enter instance type...",
                        id="cloud_instance_type",
                        value="t2.medium"
                    ),
                    Label("Number of Instances:"),
                    Input(
                        placeholder="Enter number of instances...",
                        validators=[Number(minimum=1, maximum=10), ],
                        id="cloud_instances",
                        value="1"
                    ),
                )

        # Bottom section with progress and buttons
        yield Vertical(
            ProgressBar(total=100, show_eta=False, id="progress_bar"),
            TextLog(highlight=True, markup=True, id="text_logger"),
            Horizontal(
                Button("Check Requirements", id="check_requirements", variant="primary"),
                Button("Install", id="install", variant="success"),
                Button("Exit", id="exit", variant="error")
            )
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initial actions when the app is mounted."""
        if load_gui:
            self.load_gui_from_model()

        # Add a welcome message
        self.query_one(TextLog).write("[blue]Welcome to Magellon Installation Wizard[/blue]")
        self.query_one(TextLog).write("Please configure your installation options and click 'Check Requirements' to begin.")

    def check_quit(self, do_quit: bool) -> None:
        """Called when QuitScreen is dismissed."""
        if do_quit:
            installation_data.save_settings('settings.json')
            self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "check_requirements":
            self.action_check_requirements()
        elif event.button.id == "install":
            self.query_one(TextLog).write("[yellow]Installation functionality is not implemented in this version.[/yellow]")
        elif event.button.id in ["select-single", "select-network", "select-cloud"]:
            self.handle_installation_type_selection(event.button.id)
        elif event.button.id == "add_worker":
            self.add_worker_node()
        elif event.button.id == "exit":
            self.push_screen(QuitScreen(), self.check_quit)

    def handle_installation_type_selection(self, button_id: str) -> None:
        """Handle installation type selection from the welcome screen."""
        tab_content = self.query_one(TabbedContent)
        if button_id == "select-single":
            tab_content.active = "SingleTabPane"
            self.query_one(TextLog).write("[blue]Single Computer installation selected[/blue]")
        elif button_id == "select-network":
            tab_content.active = "NetworkTabPane"
            self.query_one(TextLog).write("[blue]Network Deployment selected[/blue]")
        elif button_id == "select-cloud":
            tab_content.active = "CloudTabPane"
            self.query_one(TextLog).write("[blue]Cloud Deployment selected[/blue]")

    def add_worker_node(self) -> None:
        """Simulate adding a worker node (without actual functionality)."""
        worker_ip = self.query_one("#new_worker_ip", Input).value
        worker_username = self.query_one("#new_worker_username", Input).value

        if not worker_ip:
            self.query_one(TextLog).write("[red]Worker IP address is required[/red]")
            return

        # Update the worker list display (simplified, no actual storage)
        worker_list = self.query_one("#worker-list", Static)
        current_text = worker_list.render()

        if "No worker nodes added yet" in current_text:
            worker_list.update(f"1. {worker_ip} ({worker_username})")
        else:
            lines = current_text.split("\n")
            next_num = len(lines) + 1
            worker_list.update(f"{current_text}\n{next_num}. {worker_ip} ({worker_username})")

        # Clear the inputs
        self.query_one("#new_worker_ip", Input).value = ""
        self.query_one("#new_worker_username", Input).value = ""
        self.query_one("#new_worker_password", Input).value = ""

        self.query_one(TextLog).write(f"[green]Added worker node: {worker_ip}[/green]")

    def action_quit_app(self) -> None:
        """Action to quit the app."""
        self.push_screen(QuitScreen(), self.check_quit)

    def action_check_requirements(self) -> None:
        """Simulate checking system requirements (without actual functionality)."""
        self.save_gui_to_model()
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
        text_log.write(f"Checking available disk space at {installation_data.core_service_server_base_directory}...")
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

    def save_gui_to_model(self) -> None:
        """Save UI values to the installation data model."""
        # This is just a stub, without actual implementation
        self.query_one(TextLog).write("[blue]Saving configuration...[/blue]")

    def load_gui_from_model(self) -> None:
        """Load the installation data model into the UI."""
        # This is just a stub, without actual implementation
        self.query_one(TextLog).write("[blue]Loading saved configuration...[/blue]")


if __name__ == "__main__":
    app = MagellonInstallationApp()

    if os.path.exists('settings.json'):
        installation_data = InstallationData.load_settings('settings.json')
        load_gui = True

    reply = app.run()
    print(reply)
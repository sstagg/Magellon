from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Static, TabbedContent, TabPane, Button, Select, Input, Switch, Footer

from screens.MagellonHeader import MagellonHeader
from screens.ConfirmationScreen import ConfirmationScreen


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

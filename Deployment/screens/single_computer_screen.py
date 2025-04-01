"""
Configuration screen for single computer installation.
"""

import os
import subprocess
import re
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Static, TabbedContent, TabPane, Input, Button, Switch, Footer, Label

from header import MagellonHeader
from screens.confirmation_screen import ConfirmationScreen
from screens.requirements_screen import RequirementsScreen
from libs.utils import detect_cuda_version

class SingleComputerScreen(Screen):
    """Configuration screen for single computer installation."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="q", action="quit_app", description="Quit"),
    ]

    def __init__(self):
        super().__init__()
        # Detect CUDA version on initialization
        self.detected_cuda_version = detect_cuda_version()

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

                    # Installation directory input with full width
                    yield Static("Installation Directory:", classes="input-label")
                    yield Input(
                        placeholder="Enter installation directory",
                        id="install_dir",
                        value=str(self.app.installation_data.install_dir)
                    )

                    # CUDA version with auto-detection and confirmation
                    yield Static("CUDA Configuration:", classes="section-title")

                    with Horizontal(id="cuda-detection"):
                        yield Label("Detected CUDA Version:", classes="cuda-label")
                        yield Label(self.detected_cuda_version, id="detected-cuda-version", classes="cuda-value")

                    with Grid(id="cuda-info-grid", classes="form-grid"):
                        yield Label("CUDA Version:", classes="grid-label")
                        yield Input(
                            placeholder="CUDA version",
                            id="cuda_version",
                            value=self.detected_cuda_version,
                        )

                        yield Label("CUDA Image:", classes="grid-label")
                        yield Input(
                            placeholder="CUDA image",
                            id="cuda_image",
                            value=self.app.installation_data.cuda_image,
                        )

                        yield Label("MotionCor Binary:", classes="grid-label")
                        yield Input(
                            placeholder="MotionCor binary",
                            id="motioncor_binary",
                            value=self.app.installation_data.motioncor_binary,
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

    def save_config(self) -> None:
        """Save configuration values to the installation data."""
        # Save general settings
        self.app.installation_data.install_dir = Path(self.query_one("#install_dir").value)
        self.app.installation_data.cuda_version = self.query_one("#cuda_version").value
        self.app.installation_data.cuda_image = self.query_one("#cuda_image").value
        self.app.installation_data.motioncor_binary = self.query_one("#motioncor_binary").value
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

        # Save the configuration to disk
        self.app.save_configuration(prompt_on_success=False)

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Set cuda version field to detected CUDA version
        cuda_version_input = self.query_one("#cuda_version", Input)
        cuda_version_input.value = self.detected_cuda_version

        # Set the CUDA image and MotionCor binary based on detected version
        self.update_cuda_info(self.detected_cuda_version)

    def update_cuda_info(self, cuda_version: str) -> None:
        """Update CUDA image and MotionCor binary based on CUDA version."""
        # Define mappings from CUDA versions to image and binary
        cuda_mapping = {
            "11.1.1": {
                "image": "nvidia/cuda:11.1.1-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda111_Mar312023"
            },
            "11.2": {
                "image": "nvidia/cuda:11.2.2-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda112_Mar312023"
            },
            "11.3": {
                "image": "nvidia/cuda:11.3.1-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda113_Mar312023"
            },
            "11.4": {
                "image": "nvidia/cuda:11.4.3-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda114_Mar312023"
            },
            "11.5": {
                "image": "nvidia/cuda:11.5.2-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda115_Mar312023"
            },
            "11.6": {
                "image": "nvidia/cuda:11.6.1-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda116_Mar312023"
            },
            "11.7": {
                "image": "nvidia/cuda:11.7.1-devel-ubuntu20.04",
                "motioncor": "MotionCor2_1.6.4_Cuda117_Mar312023"
            },
            "11.8": {
                "image": "nvidia/cuda:11.8.0-devel-ubuntu22.04",
                "motioncor": "MotionCor2_1.6.4_Cuda118_Mar312023"
            },
            "12.1": {
                "image": "nvidia/cuda:12.1.0-devel-ubuntu22.04",
                "motioncor": "MotionCor2_1.6.4_Cuda121_Mar312023"
            }
        }

        # Normalize CUDA version
        version_parts = cuda_version.split('.')
        if len(version_parts) > 2:
            # Handle special case for 11.1.1
            if version_parts[0] == "11" and version_parts[1] == "1" and version_parts[2] != "0":
                norm_version = "11.1.1"
            else:
                # Otherwise just take major.minor
                norm_version = f"{version_parts[0]}.{version_parts[1]}"
        else:
            norm_version = cuda_version

        # Update the fields
        cuda_image_input = self.query_one("#cuda_image", Input)
        motioncor_binary_input = self.query_one("#motioncor_binary", Input)

        if norm_version in cuda_mapping:
            cuda_image_input.value = cuda_mapping[norm_version]["image"]
            motioncor_binary_input.value = cuda_mapping[norm_version]["motioncor"]
        else:
            # Fallback to default values
            cuda_image_input.value = self.app.installation_data.cuda_image
            motioncor_binary_input.value = self.app.installation_data.motioncor_binary
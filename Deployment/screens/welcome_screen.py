"""
Welcome screen for the Magellon installation wizard.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.screen import Screen
from textual.widgets import Static, Button, Footer


from screens.single_computer_screen import SingleComputerScreen
from screens.help_screen import HelpScreen

from header import MagellonHeader
from screens.quit_screen import QuitScreen

class WelcomeScreen(Screen):
    """Welcome screen for the Magellon installation wizard."""

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
        Binding(key="?", action="show_help", description="Help"),
    ]

    def compose(self) -> ComposeResult:
        yield MagellonHeader()

        with Container(id="welcome-container"):
            yield Static("MAGELLON INSTALLER", id="logo")
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
            self.app.notify("Network deployment is not implemented in this version")
        elif button_id == "select-cloud":
            self.app.notify("Cloud deployment is not implemented in this version")
        elif button_id == "exit-button":
            self.app.push_screen(QuitScreen(), self.app.check_quit)

    def action_show_help(self) -> None:
        """Show help information."""
        self.app.push_screen(HelpScreen())
"""
Help screen with information about the wizard.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, TabbedContent, TabPane, Button, Footer

from header import MagellonHeader


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
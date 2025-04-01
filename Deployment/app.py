"""
Main Magellon Installation application class.
"""

import os
import json
from pathlib import Path

from textual.app import App
from textual.binding import Binding
from textual.widgets import Footer

from libs.models import InstallationData
from screens.welcome_screen import WelcomeScreen
from screens.help_screen import HelpScreen
from screens.quit_screen import QuitScreen

class MagellonInstallationApp(App):
    """Enhanced Magellon Installation Wizard."""

    CSS_PATH = "config.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Next-gen CryoEm Software"

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit"),
        Binding(key="?", action="show_help", description="Help"),
    ]

    SCREENS = {
        "welcome_screen": WelcomeScreen,
        "quit_screen": QuitScreen,
        "help_screen": HelpScreen,
    }

    def __init__(self):
        super().__init__()
        self.installation_data = InstallationData()
        self.config_file = Path.home() / ".magellon_config.json"
        self.load_configuration()

    def on_mount(self) -> None:
        """Initial actions when the app is mounted."""
        # Display the welcome screen
        self.push_screen(WelcomeScreen())

    def action_quit_app(self) -> None:
        """Action to quit the app."""
        self.push_screen(QuitScreen(), self.check_quit)

    def action_show_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def check_quit(self, do_quit: bool) -> None:
        """Called when QuitScreen is dismissed."""
        if do_quit:
            self.exit()

    def save_configuration(self, prompt_on_success: bool = True) -> None:
        """Save current configuration to a file."""
        try:
            # Convert installation data to dictionary
            config_dict = vars(self.installation_data)

            # Convert Path objects to strings
            for key, value in config_dict.items():
                if isinstance(value, Path):
                    config_dict[key] = str(value)

            # Write configuration to file
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)

            if prompt_on_success:
                self.notify(f"Configuration saved to {self.config_file}")
        except Exception as e:
            self.notify(f"Failed to save configuration: {str(e)}", severity="error")

    def load_configuration(self) -> bool:
        """Load configuration from file if it exists."""
        if not self.config_file.exists():
            return False

        try:
            with open(self.config_file, 'r') as f:
                config_dict = json.load(f)

            # Update installation data with loaded configuration
            for key, value in config_dict.items():
                if hasattr(self.installation_data, key):
                    # Convert string paths back to Path objects if needed
                    if key.endswith('_dir') and isinstance(value, str):
                        value = Path(value)

                    setattr(self.installation_data, key, value)

            return True
        except Exception as e:
            self.notify(f"Failed to load configuration: {str(e)}", severity="warning")
            return False
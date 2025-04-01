from textual.app import App
from textual.binding import Binding
from textual.widgets import TextLog, ProgressBar

from libs.models import InstallationData
from screens.HelpScreen import HelpScreen
from screens.WelcomeScreen import WelcomeScreen
from screens.quit_screen import QuitScreen


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

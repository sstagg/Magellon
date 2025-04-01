from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Horizontal


class QuitScreen(Screen[bool]):
    """Screen that asks for confirmation before quitting."""

    def compose(self) -> ComposeResult:
        yield Static("Do you want to exit Magellon Installation Wizard?", id="quit-question")
        yield Static("Any unsaved configuration will be lost.", id="quit-warning")

        with Horizontal(id="quit-buttons"):
            yield Button("No, continue installation", variant="primary", id="continue-btn")
            yield Button("Yes, exit", variant="error", id="exit-btn")
            yield Button("Save settings and exit", variant="warning", id="save-exit-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "continue-btn":
            # Return False to indicate that the user doesn't want to quit
            self.dismiss(False)
        elif event.button.id == "exit-btn":
            # Return True to indicate that the user wants to quit without saving
            self.dismiss(True)
        elif event.button.id == "save-exit-btn":
            # Return True with a side effect of saving settings in the calling function
            self.app.save_configuration()
            self.dismiss(True)